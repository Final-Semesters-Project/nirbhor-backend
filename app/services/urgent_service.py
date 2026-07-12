from datetime import datetime, timezone
from typing import cast
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
from app.core.exceptions import DomainIntegrityError, DomainValidationError
from app.core.i18n import t
from app.models.skill_model import Skill
from app.models.urgent_broadcast_model import BroadcastStatus
from app.repositories.skill_repository import SkillRepository
from app.repositories.urgent_repository import UrgentBroadcastRepository
from app.repositories.user_repository import UserRepository
from app.schemas.urgent_schema import BroadcastStatusResponseForSeeker, UrgentBroadcastCreateSchema, UrgentBroadcastDetailResponse, UrgentBroadcastCreateResponse, ClaimedBroadcastResponseToProvider
from app.services.notification_service import NotificationService


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

        skill_name_en = skill_row.name_en
        skill_name_bn = skill_row.name_bn or skill_name_en

        # 1. Create the broadcast row
        broadcast = await urgent_repo.create_broadcast(
            seeker_id=seeker_id,
            skill_id=data.skill_id,
            latitude=data.latitude,
            longitude=data.longitude,
        )

        # 2. Find nearby provider FCM tokens (within 3 KM, has_smartphone=True)
        tokens = await urgent_repo.get_nearby_fcm_tokens_to_create_urgent_broadcast_notification(
            latitude=data.latitude,
            longitude=data.longitude,
            skill_id=data.skill_id,
            radius_km=3,
        )

        await db.commit()

        # 3. Fire FCM to all nearby providers simultaneously (stub)
        if tokens:
            logger.info(
                f"Urgent broadcast {broadcast.id}: sending FCM to {len(tokens)} providers"
            )
            await NotificationService.send_urgent_broadcast_to_providers(
                tokens=tokens,
                broadcast_id=broadcast.id,
                skill_name_en=skill_name_en,
                skill_name_bn=skill_name_bn
            )
        else:
            logger.warning(
                f"Urgent broadcast {broadcast.id}: no nearby smartphone providers found"
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

        if broadcast.status == BroadcastStatus.EXPIRED:
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
