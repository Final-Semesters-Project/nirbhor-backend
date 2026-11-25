from datetime import datetime, timezone
from typing import cast
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
from app.core.exceptions import DomainIntegrityError, DomainValidationError
from app.core.geo import to_lat_lng
from app.core.i18n import t
from app.core.paginator import paginate
from app.models.skill_model import Skill
from app.models.urgent_broadcast_model import BroadcastStatus, UrgentBroadcast
from app.models.user_model import Role
from app.repositories.skill_repository import SkillRepository
from app.repositories.urgent_repository import UrgentBroadcastRepository
from app.repositories.user_repository import UserRepository
from app.schemas.pagination_schema import PageResponse
from app.schemas.urgent_schema import BroadcastStatusResponseForSeeker, CompleteUrgentBroadcastResponse, ProviderCancelBroadcastResponse, ProviderUrgentBroadcastItem, SeekerUrgentBroadcastItem, UrgentBroadcastCancelResponse, UrgentBroadcastCreateSchema, UrgentBroadcastDetailResponse, UrgentBroadcastCreateResponse, ClaimedBroadcastResponseToProvider
from app.services.notification_service import NotificationService
from geoalchemy2.shape import to_shape


class UrgentService:

    @staticmethod
    async def create_broadcast(
        data: UrgentBroadcastCreateSchema,
        seeker_id: UUID,
        db: AsyncSession,
        lang: str,
    ) -> UrgentBroadcastCreateResponse:
        """
        This is the first step of creating an urgent broadcast.
        Seeker triggers 'Need It NOW/Urgent'.
        """
        urgent_repo = UrgentBroadcastRepository(db)
        skill_repo = SkillRepository(db)

        skill_row = await skill_repo.get_skill_names(skill_id=data.skill_id)

        if not skill_row:
            raise DomainValidationError(t("invalid_skill_ids", lang))

        # 1. Eligibility check first. Nothing is inserted if nobody can be reached.
        tokens = await urgent_repo.get_nearby_fcm_tokens(
            latitude=data.latitude, longitude=data.longitude,
            skill_id=data.skill_id, radius_km=3,
        )

        if not tokens:
            logger.error(
                f"Urgent request by {seeker_id}: no reachable providers, no broadcast created")
            return UrgentBroadcastCreateResponse(
                broadcast_id=None, status="no_providers", expires_at=None,
                message=t("no_providers_nearby", lang),
            )

        skill_name_en = skill_row.name_en
        skill_name_bn = skill_row.name_bn or skill_name_en

        # 2. Create the broadcast row if eligible
        broadcast = await urgent_repo.create_broadcast(
            seeker_id=seeker_id,
            skill_id=data.skill_id,
            latitude=data.latitude,
            longitude=data.longitude,
        )
        logger.success("Broadcast created")

        await db.commit()

        # 3. Fire FCM to all nearby providers simultaneously

        logger.info(
            f"Urgent broadcast {broadcast.id}: sending FCM to {len(tokens)} providers"
        )
        await NotificationService.send_urgent_broadcast_to_providers(
            tokens=tokens,
            broadcast_id=broadcast.id,
            skill_name_en=skill_name_en,
            skill_name_bn=skill_name_bn,
            preferred_lang=lang,
        )

        return UrgentBroadcastCreateResponse(
            broadcast_id=broadcast.id,
            status=broadcast.status,
            expires_at=broadcast.expires_at,
            message=t("broadcast_created", lang),
        )

    @staticmethod
    async def get_broadcast(
        broadcast_id: UUID,
        db: AsyncSession,
        lang: str,
    ) -> UrgentBroadcastDetailResponse:
        """
        This is the third step of urgent broadcast. After provider taps the FCM notification. The app opens and fetches the broadcast details.
        Returns location so provider can navigate.
        """
        from geoalchemy2.shape import to_shape

        urgent_repo = UrgentBroadcastRepository(db)
        broadcast = await urgent_repo.get_broadcast_by_id(broadcast_id)

        if not broadcast:
            raise DomainValidationError(t("broadcast_not_found", lang))

        # get the skill name for the broadcast
        name_col = Skill.name_bn if lang == "bn" else Skill.name_en
        result = await db.execute(
            select(name_col).where(Skill.id == broadcast.skill_id)
        )
        skill_name = result.scalar_one_or_none() or ""

        from shapely.geometry import Point
        # Extract lat/lng from the PostGIS point
        lat, lng = None, None
        if broadcast.location is not None:
            point = cast(Point, to_shape(broadcast.location))
            lng = point.x   # PostGIS stores as (lng, lat)
            lat = point.y

        return UrgentBroadcastDetailResponse(
            broadcast_id=broadcast.id,
            status=broadcast.status,
            skill_id=broadcast.skill_id,
            skill_name=skill_name,
            expires_at=broadcast.expires_at,
            seeker_latitude=lat,
            seeker_longitude=lng,
        )

    @staticmethod
    async def claim_broadcast(
        broadcast_id: UUID,
        provider_id: UUID,
        db: AsyncSession,
        lang: str,
    ) -> ClaimedBroadcastResponseToProvider:
        """
        Atomic claim — only the first provider to hit this wins.
        Uses with_for_update() pessimistic lock in the repository.
        """
        urgent_repo = UrgentBroadcastRepository(db)
        user_repo = UserRepository(db)

        broadcast = await urgent_repo.claim_a_broadcast_by_provider(broadcast_id, provider_id)

        if not broadcast:
            raise DomainValidationError(t("broadcast_not_found", lang))

        if broadcast.status in (BroadcastStatus.EXPIRED, BroadcastStatus.CANCELLED):
            raise DomainValidationError(t("broadcast_not_found", lang))

        if broadcast.status == BroadcastStatus.CLAIMED:
            if broadcast.claimed_by_provider_id != provider_id:
                # Someone else claimed it first
                raise DomainIntegrityError(
                    t("broadcast_already_claimed", lang))

        seeker = await user_repo.get_by_id(broadcast.seeker_id)

        if not seeker:
            raise DomainIntegrityError(t("seeker_not_found", lang))

        # If broadcast was already claimed or expired by the time we locked it
        if broadcast.status == BroadcastStatus.CLAIMED:
            if broadcast.claimed_by_provider_id == provider_id:
                # This provider already claimed it (duplicate tap) — idempotent OK
                # Fetch seeker for the response (no FCM — already sent on first claim)
                await db.commit()
                return (
                    ClaimedBroadcastResponseToProvider(
                        broadcast_id=broadcast.id,
                        status=BroadcastStatus.CLAIMED,
                        seeker_phone=seeker.phone_en if seeker else "",
                        seeker_name=((seeker.name_bn or seeker.name_en) if lang ==
                                     "bn" else seeker.name_en) if seeker else "",
                    )
                )

        # ── Successful first claim ────────────────────────────────────────────────
        await db.commit()

        logger.info(
            f"Broadcast {broadcast_id} claimed by provider {provider_id}")

        # Fetch notification data — seeker FCM + provider name — one query
        notification_data = await urgent_repo.get_claim_notification_data(
            seeker_id=broadcast.seeker_id,
            provider_id=provider_id,
        )

        if notification_data and notification_data.seeker_fcm_token:
            await NotificationService.send_broadcast_claimed_to_seeker(
                seeker_fcm_token=notification_data.seeker_fcm_token,
                provider_name_en=notification_data.provider_name_en,
                provider_name_bn=notification_data.provider_name_bn,
                preferred_lang=notification_data.seeker_preferred_lang,
            )
        else:
            logger.warning(
                f"No FCM token for seeker {broadcast.seeker_id} "
                f"— skipping claim notification"
            )

        return (
            ClaimedBroadcastResponseToProvider(
                broadcast_id=broadcast.id,
                status=broadcast.status,
                seeker_phone=seeker.phone_en,
                seeker_name=(
                    (seeker.name_bn or seeker.name_en) if lang ==
                    "bn" else seeker.name_en) if seeker else "",
            )
        )

    @staticmethod
    async def complete_broadcast(
        broadcast_id: UUID,
        user_id: UUID,
        db: AsyncSession,
        lang: str,
    ) -> CompleteUrgentBroadcastResponse:
        """
        Atomic completion by either the broadcast's Seeker or the assigned Provider.
        Pessimistic lock ensures only the first caller triggers FCM notifications;
        a simultaneous second tap returns 409 Conflict (or idempotent 200 if desired).
        """
        urgent_repo = UrgentBroadcastRepository(db)
        broadcast, just_completed = await urgent_repo.complete_a_broadcast(broadcast_id)

        if not broadcast:
            raise DomainValidationError(t("broadcast_not_found", lang))

        # Ownership check: only this broadcast's seeker or assigned provider can complete it
        if user_id not in (broadcast.seeker_id, broadcast.claimed_by_provider_id):
            raise DomainValidationError(t("broadcast_cannot_complete", lang))

        # Already completed before we acquired the lock (e.g. the other party tapped first)
        if not just_completed:
            if broadcast.status == BroadcastStatus.COMPLETED:
                raise DomainIntegrityError(
                    t("broadcast_already_completed", lang))
            raise DomainValidationError(t("broadcast_cannot_complete", lang))

        # Save provider_id before commit (though it stays on the row)
        provider_id = broadcast.claimed_by_provider_id
        completed_at = broadcast.completed_at

        await db.commit()

        logger.info(
            f"Urgent broadcast {broadcast_id} marked COMPLETED by user {user_id}")

        # Notify both Seeker and Provider
        if provider_id:
            notification_data = await urgent_repo.get_completed_notification_data(
                seeker_id=broadcast.seeker_id,
                provider_id=provider_id,
            )

            if notification_data:
                if notification_data.seeker_fcm_token:
                    await NotificationService.send_broadcast_completed(
                        fcm_token=notification_data.seeker_fcm_token,
                        other_party_name_en=notification_data.provider_name_en,
                        other_party_name_bn=notification_data.provider_name_bn,
                        preferred_lang=notification_data.seeker_preferred_lang,
                        recipient_role=Role.SEEKER,
                        broadcast_id=broadcast_id
                    )
                else:
                    logger.warning(
                        f"No FCM token for seeker {broadcast.seeker_id} — skipping completion push")

                if notification_data.provider_fcm_token:
                    await NotificationService.send_broadcast_completed(
                        fcm_token=notification_data.provider_fcm_token,
                        other_party_name_en=notification_data.seeker_name_en,
                        other_party_name_bn=notification_data.seeker_name_bn,
                        preferred_lang=notification_data.provider_preferred_lang,
                        recipient_role=Role.PROVIDER,
                        broadcast_id=broadcast_id
                    )
                else:
                    logger.warning(
                        f"No FCM token for provider {provider_id} — skipping completion push")

        return CompleteUrgentBroadcastResponse(
            broadcast_id=broadcast.id,
            status=broadcast.status,
            completed_at=completed_at,  # type: ignore[arg-type]
            message=t("broadcast_completed", lang),
        )

    @staticmethod
    async def get_broadcast_status(
        broadcast_id: UUID,
        db: AsyncSession,
        lang: str,
    ) -> BroadcastStatusResponseForSeeker:
        urgent_repo = UrgentBroadcastRepository(db)
        data = await urgent_repo.get_broadcast_status(broadcast_id)

        if not data:
            raise DomainValidationError(t("broadcast_not_found", lang))
        return BroadcastStatusResponseForSeeker(**data)

    @staticmethod
    async def cancel_broadcast(
        broadcast_id: UUID,
        db: AsyncSession,
        lang: str,
        current_user_id: UUID,
    ):
        urgent_repo = UrgentBroadcastRepository(db)

        # check if broadcast exists and is BROADCASTING
        broadcast = await urgent_repo.get_broadcast_by_id(broadcast_id)
        if not broadcast or broadcast.status != BroadcastStatus.BROADCASTING:
            raise DomainValidationError(t("broadcast_not_found", lang))

        cancelled = await urgent_repo.cancel_broadcast(
            broadcast_id=broadcast_id,
            seeker_id=current_user_id,
        )

        if not cancelled:
            await db.rollback()
            raise DomainIntegrityError(t("broadcast_not_found", lang))

        await db.commit()

        return UrgentBroadcastCancelResponse(
            broadcast_id=broadcast_id,
            status=BroadcastStatus.CANCELLED,
            message=t("broadcast_cancelled", lang),
        )

    @staticmethod
    async def get_seeker_broadcasts(
        seeker_id: UUID, db: AsyncSession, lang: str,
        page: int = 1, page_size: int = 10,
        status: BroadcastStatus | None = None, active_only: bool = False,
    ) -> PageResponse[SeekerUrgentBroadcastItem]:
        urgent_repo = UrgentBroadcastRepository(db)
        now = datetime.now(timezone.utc)

        def transform(row):
            b, skill_name, provider_name, provider_phone = row
            return SeekerUrgentBroadcastItem(
                broadcast_id=b.id, status=b.status, skill_id=b.skill_id,
                skill_name=skill_name or "", created_at=b.created_at, expires_at=b.expires_at,
                seconds_remaining=(max(0, int((b.expires_at - now).total_seconds()))
                                   if b.status == BroadcastStatus.BROADCASTING else None),
                cancelled_at=b.cancelled_at, provider_name=provider_name,
                provider_phone=provider_phone if b.status == BroadcastStatus.CLAIMED else None,
            )

        return await paginate(
            db=db,
            stmt=urgent_repo.get_seeker_broadcasts_stmt(
                seeker_id, lang, status, active_only),
            pk_col=UrgentBroadcast.id, page=page, page_size=page_size, transformer=transform,
        )

    @staticmethod
    async def get_provider_broadcasts(
        provider_id: UUID, db: AsyncSession, lang: str,
        page: int = 1, page_size: int = 10,
        status: BroadcastStatus | None = None, active_only: bool = False,
    ) -> PageResponse[ProviderUrgentBroadcastItem]:
        urgent_repo = UrgentBroadcastRepository(db)

        def transform(row):
            b, skill_name, seeker_name, seeker_phone = row
            active = b.status == BroadcastStatus.CLAIMED
            lat = lng = None
            if active and b.location is not None:       # location shared only while the job is active
                point = to_lat_lng(b.location)

                lat, lng = point if point else (None, None)

            return ProviderUrgentBroadcastItem(
                broadcast_id=b.id, status=b.status, skill_id=b.skill_id,
                skill_name=skill_name or "", created_at=b.created_at, cancelled_at=b.cancelled_at,
                seeker_name=seeker_name or "", seeker_phone=seeker_phone if active else None,
                seeker_latitude=lat, seeker_longitude=lng,
            )

        return await paginate(
            db=db,
            stmt=urgent_repo.get_provider_broadcasts_stmt(
                provider_id, lang, status, active_only),
            pk_col=UrgentBroadcast.id, page=page, page_size=page_size, transformer=transform,
        )

    @staticmethod
    async def cancel_broadcast_by_provider(
        broadcast_id: UUID, provider_id: UUID, db: AsyncSession, lang: str,
    ) -> ProviderCancelBroadcastResponse:
        """Provider releases an accepted job. Idempotent: a repeat call returns the same result."""
        urgent_repo = UrgentBroadcastRepository(db)

        broadcast, changed = await urgent_repo.cancel_claimed_broadcast_by_provider(
            broadcast_id, provider_id)
        if broadcast is None:                       # unknown id or not this provider's job
            raise DomainValidationError(t("broadcast_not_found", lang))
        if not changed and broadcast.status != BroadcastStatus.CANCELLED:
            raise DomainValidationError(
                t("broadcast_cancel_not_allowed", lang))

        # the cancel is final before any push goes out
        await db.commit()

        if changed:
            data = await urgent_repo.get_claim_notification_data(
                seeker_id=broadcast.seeker_id, provider_id=provider_id)
            if data and data.seeker_fcm_token:
                await NotificationService.send_broadcast_cancelled_to_seeker(
                    seeker_fcm_token=data.seeker_fcm_token,
                    provider_name_en=data.provider_name_en,
                    provider_name_bn=data.provider_name_bn,
                    preferred_lang=data.seeker_preferred_lang,
                    broadcast_id=broadcast.id,
                )
            else:
                logger.warning(
                    f"No FCM token for seeker {broadcast.seeker_id}; skipped cancel push")

        return ProviderCancelBroadcastResponse(
            broadcast_id=broadcast.id, status=broadcast.status,
            message=t("broadcast_cancelled_by_provider", lang))
