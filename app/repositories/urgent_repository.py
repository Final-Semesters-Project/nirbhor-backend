from datetime import datetime, timezone, timedelta
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
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

        # Fetch seeker details to return to the claiming provider
        # seeker_result = await self.db.execute(
        #     select(User.name_en, User.phone_en)
        #     .where(User.id == broadcast.seeker_id)
        # )
        # seeker_row = seeker_result.first()
        # seeker_name = seeker_row.name_en if seeker_row else "—"
        # seeker_phone = seeker_row.phone_en if seeker_row else None

        # return broadcast, seeker_name, seeker_phone

        return broadcast

    async def get_broadcast_by_id(self, broadcast_id: UUID) -> UrgentBroadcast | None:
        """Fetch a broadcast for the detail view."""
        result = await self.db.execute(
            select(UrgentBroadcast).where(UrgentBroadcast.id == broadcast_id).where(
                UrgentBroadcast.status != BroadcastStatus.EXPIRED)
        )
        return result.scalar_one_or_none()

    # TODO: check with claude later
    async def expire_stale_broadcasts(self) -> list[str]:
        """
        Mark all BROADCASTING rows past expires_at as EXPIRED.
        Returns list of seeker_fcm_tokens to notify along with the seekers preferred language.
        Called by APScheduler every minute.
        """
        from sqlalchemy import update
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)

        update_stmt = (
            update(UrgentBroadcast)
            .where(UrgentBroadcast.status == BroadcastStatus.BROADCASTING)
            .where(UrgentBroadcast.expires_at < now)
            .values(status=BroadcastStatus.EXPIRED)
            .returning(UrgentBroadcast.seeker_id)
            # Turns the update into an inline temporary table
        ).cte("updated_broadcasts")

        # join the update results directly to the FCM token table
        query = (
            select(FCMToken.token, User.preferred_lang)
            .join(update_stmt, FCMToken.user_id == update_stmt.c.seeker_id)
            .join(User, User.id == update_stmt.c.seeker_id)
            .where(FCMToken.token.is_not(None))
        )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_broadcast_status(
        self, broadcast_id: UUID
    ) -> dict | None:
        """Fetch broadcast + claimed provider name if claimed."""
        from app.models.user_model import User as UserModel

        ClaimedProvider = aliased(UserModel, name="claimed_provider")

        result = await self.db.execute(
            select(UrgentBroadcast, ClaimedProvider.name_en.label("claimed_name"))
            .outerjoin(
                ClaimedProvider,
                UrgentBroadcast.claimed_by_provider_id == ClaimedProvider.id,
            )
            .where(UrgentBroadcast.id == broadcast_id)
        )
        row = result.first()
        if not row:
            return None

        broadcast, claimed_name = row

        seconds_remaining = max(
            0,
            int((broadcast.expires_at - datetime.now(timezone.utc)).total_seconds())
        )

        return {
            "broadcast_id": broadcast.id,
            "status": broadcast.status,
            "expires_at": broadcast.expires_at,
            "claimed_by_name": claimed_name,
            "seconds_remaining": seconds_remaining,
            # "claimed_at": None,  # add claimed_at column to model if needed
        }
