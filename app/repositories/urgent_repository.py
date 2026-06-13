from datetime import datetime, timezone, timedelta
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.fcm_token import FCMToken
from app.models.provider_profile_model import ProviderProfile
from app.models.urgent_broadcast_model import BroadcastStatus, UrgentBroadcast
from geoalchemy2.functions import ST_DWithin, ST_MakePoint, ST_SetSRID
from geoalchemy2 import Geography

from app.models.user_model import User


class UrgentBroadcastRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_broadcast(
        self,
        seeker_id: UUID,
        skill_id: int,
        latitude: float,
        longitude: float,
    ) -> UrgentBroadcast:
        point = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
        broadcast = UrgentBroadcast(
            seeker_id=seeker_id,
            skill_id=skill_id,
            location=point,
            status=BroadcastStatus.BROADCASTING,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
        self.db.add(broadcast)
        await self.db.flush()
        return broadcast

    async def get_nearby_fcm_tokens(
        self,
        latitude: float,
        longitude: float,
        radius_km: int = 3,
    ) -> list[str]:
        """
        Find FCM tokens for providers within radius_km who have smartphones.
        Returns list of token strings for batch FCM send.
        """
        seeker_point = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
        radius_m = radius_km * 1000

        result = await self.db.execute(
            select(FCMToken.token)
            .join(ProviderProfile, FCMToken.user_id == ProviderProfile.user_id)
            .where(ProviderProfile.has_smartphone == True)
            .where(ProviderProfile.is_available == True)
            .where(User.is_active == True)
            .where(
                ST_DWithin(
                    ProviderProfile.base_location.cast(Geography),
                    seeker_point.cast(Geography),
                    radius_m,
                )
            )
            .where(
                ST_DWithin(
                    ProviderProfile.base_location.cast(Geography),
                    seeker_point.cast(Geography),
                    ProviderProfile.working_radius_km * 1000
                )
            )
        )
        return [row.token for row in result.all()]

    async def claim_broadcast(
        self,
        broadcast_id: UUID,
        provider_id: UUID,
    ) -> UrgentBroadcast | None:
        """
        Atomic claim with pessimistic lock.
        Returns the broadcast if successfully claimed, None if already taken.
        """
        # with_for_update() locks the row until this transaction commits
        result = await self.db.execute(
            select(UrgentBroadcast)
            .where(UrgentBroadcast.id == broadcast_id)
            .with_for_update()
        )
        broadcast = result.scalar_one_or_none()

        if not broadcast:
            return None

        if broadcast.status != BroadcastStatus.BROADCASTING:
            # Already claimed or expired — return the broadcast so the service
            # can produce the right error message
            return broadcast

        broadcast.status = BroadcastStatus.CLAIMED
        broadcast.claimed_by_provider_id = provider_id
        await self.db.flush()
        return broadcast
