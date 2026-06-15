from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
from app.core.exceptions import DomainIntegrityError, DomainValidationError
from app.core.i18n import t
from app.models.urgent_broadcast_model import BroadcastStatus
from app.repositories.urgent_repository import UrgentBroadcastRepository
from app.repositories.user_repository import UserRepository
from app.schemas.urgent_schema import UrgentBroadcastCreateSchema, UrgentBroadcastResponse, ClaimedBroadcastResponse


class UrgentService:

    @staticmethod
    async def create_broadcast(
        data: UrgentBroadcastCreateSchema,
        seeker_id: UUID,
        db: AsyncSession,
        lang: str,
    ) -> UrgentBroadcastResponse:

        urgent_repo = UrgentBroadcastRepository(db)

        # 1. Create the broadcast row
        broadcast = await urgent_repo.create_broadcast(
            seeker_id=seeker_id,
            skill_id=data.skill_id,
            latitude=data.latitude,
            longitude=data.longitude,
        )

        # 2. Find nearby provider FCM tokens (within 3 KM, has_smartphone=True)
        tokens = await urgent_repo.get_nearby_fcm_tokens(
            latitude=data.latitude,
            longitude=data.longitude,
            radius_km=3,
        )

        await db.commit()

        # 3. Fire FCM to all nearby providers simultaneously (stub)
        if tokens:
            logger.info(
                f"Urgent broadcast {broadcast.id}: sending FCM to {len(tokens)} providers"
            )
            # TODO: await NotificationService.send_urgent_broadcast(tokens, broadcast.id, skill_id)
        else:
            logger.warning(
                f"Urgent broadcast {broadcast.id}: no nearby smartphone providers found"
            )

        return UrgentBroadcastResponse(
            broadcast_id=broadcast.id,
            status=broadcast.status,
            expires_at=broadcast.expires_at,
            message=t("broadcast_created", lang),
        )

    @staticmethod
    async def claim_broadcast(
        broadcast_id: UUID,
        provider_id: UUID,
        db: AsyncSession,
        lang: str,
    ) -> ClaimedBroadcastResponse:
        """
        Atomic claim — only the first provider to hit this wins.
        Uses with_for_update() pessimistic lock in the repository.
        """
        urgent_repo = UrgentBroadcastRepository(db)
        user_repo = UserRepository(db)

        broadcast = await urgent_repo.claim_broadcast(broadcast_id, provider_id)

        if not broadcast:
            raise DomainValidationError(t("broadcast_not_found", lang))

        seeker = await user_repo.get_by_id(broadcast.seeker_id)

        if not seeker:
            raise DomainIntegrityError(t("seeker_not_found", lang))

        # If broadcast was already claimed or expired by the time we locked it
        if broadcast.status == BroadcastStatus.CLAIMED:
            if broadcast.claimed_by_provider_id == provider_id:
                # This provider already claimed it (duplicate tap) — idempotent OK
                await db.commit()
                return (
                    ClaimedBroadcastResponse(
                        broadcast_id=broadcast.id,
                        status=BroadcastStatus.CLAIMED,
                        yours=True,
                        seeker_phone=seeker.phone_en,
                    )
                )
            # Another provider claimed it first
            raise DomainIntegrityError(t("broadcast_already_claimed", lang))

        if broadcast.status == BroadcastStatus.EXPIRED:
            raise DomainValidationError(t("broadcast_not_found", lang))

        await db.commit()

        logger.info(
            f"Broadcast {broadcast_id} claimed by provider {provider_id}")

        # TODO: Notify seeker that provider is on the way
        # await NotificationService.send_broadcast_claimed(broadcast.seeker_id, provider_id)

        # FIX: Shouldn't we send the seeker phone number to the provider when he claims the broadcast? so that they can communicate? After that if the provider refuse to come then the seeker can initiate another broadcast?
        return (
            ClaimedBroadcastResponse(
                broadcast_id=broadcast.id,
                status=broadcast.status,
                yours=True,
                seeker_phone=seeker.phone_en
            )
        )
