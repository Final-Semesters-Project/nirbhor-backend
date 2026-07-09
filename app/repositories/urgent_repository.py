from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from app.models.fcm_token import FCMToken
from app.models.provider_profile_model import ProviderProfile
from app.models.provider_skill_link_model import ProviderSkillLink
from app.models.skill_model import Skill
from app.models.urgent_broadcast_model import BroadcastStatus, UrgentBroadcast
from geoalchemy2.functions import ST_DWithin, ST_MakePoint, ST_SetSRID
from geoalchemy2 import Geography

from app.models.user_model import User


@dataclass
class BroadcastClaimNotificationData:
    """Everything needed to notify the seeker after a successful claim."""
    seeker_fcm_token: str | None
    seeker_preferred_lang: str
    provider_name_en: str
    provider_name_bn: str


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

    async def get_nearby_fcm_tokens_to_create_urgent_broadcast_notification(
        self,
        latitude: float,
        longitude: float,
        skill_id: int,
        radius_km: int = 3
    ) -> list[str]:
        """
        Find FCM tokens for providers within radius_km who have smartphones.
        Returns list of token strings for batch FCM send.
        """
        seeker_point = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
        radius_m = radius_km * 1000

        result = await self.db.execute(
            select(FCMToken.token)
            # FCMToken → ProviderProfile (same user_id)
            .join(ProviderProfile, FCMToken.user_id == ProviderProfile.user_id)
            # ProviderProfile → User (to check is_active)
            .join(User, User.id == ProviderProfile.user_id)
            # ProviderProfile → ProviderSkillLink (filter by skill)
            .join(
                ProviderSkillLink,
                ProviderSkillLink.provider_id == ProviderProfile.user_id,
            )
            # only providers with this skill
            .where(ProviderSkillLink.skill_id == skill_id)
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
            # Deduplicate — a provider with multiple skills would appear multiple times
            .distinct(FCMToken.token)
        )
        return [row.token for row in result.all()]

    async def claim_a_broadcast_by_provider(
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

    async def get_claim_notification_data(
        self,
        seeker_id: UUID,
        provider_id: UUID,
    ) -> BroadcastClaimNotificationData | None:
        """
        Fetch seeker FCM token + provider name in one query.
        Called only after a successful claim — not on 409 or 404 paths.
        """
        SeekerUser = aliased(User, name="seeker_user")
        ProviderUser = aliased(User, name="provider_user")

        result = await self.db.execute(
            select(
                FCMToken.token.label("seeker_fcm_token"),
                SeekerUser.preferred_lang,
                ProviderUser.name_en.label("provider_name_en"),
                ProviderUser.name_bn.label("provider_name_bn"),
            )
            # Get seeker user row
            .join(SeekerUser,   SeekerUser.id == seeker_id)
            # Get provider user row
            .join(ProviderUser, ProviderUser.id == provider_id)
            # LEFT JOIN FCMToken — seeker might not have a token registered
            .outerjoin(
                FCMToken,
                (FCMToken.user_id == seeker_id) & FCMToken.token.is_not(None)
            )
            # Use a literal select_from so SQLAlchemy has a base table
            .select_from(SeekerUser)
        )

        row = result.first()
        if not row:
            return None

        return BroadcastClaimNotificationData(
            seeker_fcm_token=row.seeker_fcm_token,
            seeker_preferred_lang=row.preferred_lang or "bn",
            provider_name_en=row.provider_name_en,
            provider_name_bn=row.provider_name_bn or row.provider_name_en,
        )

    async def get_broadcast_by_id(self, broadcast_id: UUID) -> UrgentBroadcast | None:
        """Fetch a broadcast for the detail view."""
        result = await self.db.execute(
            select(UrgentBroadcast).where(UrgentBroadcast.id == broadcast_id).where(
                UrgentBroadcast.status != BroadcastStatus.EXPIRED)
        )
        return result.scalar_one_or_none()

    async def expire_stale_broadcasts(self) -> list[tuple[str, str]]:
        """
        Mark all BROADCASTING rows past expires_at as EXPIRED.
        Returns list of (fcm_token, preferred_lang) tuples for expired seekers.
        Called by APScheduler every minute.

        Why two statements instead of CTE?
        SQLAlchemy 2.0 async does not support UPDATE...RETURNING chained as CTE
        in the same select. Two statements in the same transaction is correct,
        readable, and still atomic — no other transaction sees partial state.
        """
        from sqlalchemy import update
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)

        # Step 1: Update and get seeker_ids of expired broadcasts
        update_result = await self.db.execute(
            update(UrgentBroadcast)
            .where(UrgentBroadcast.status == BroadcastStatus.BROADCASTING)
            .where(UrgentBroadcast.expires_at < now)
            .values(status=BroadcastStatus.EXPIRED)
            .returning(UrgentBroadcast.seeker_id)
        )
        seeker_ids = [row.seeker_id for row in update_result.all()]

        if not seeker_ids:
            return []

        # Step 2: Fetch FCM tokens + language for those seekers in one query
        token_result = await self.db.execute(
            select(FCMToken.token, User.preferred_lang)
            .join(User, FCMToken.user_id == User.id)
            .where(FCMToken.user_id.in_(seeker_ids))
            .where(FCMToken.token.is_not(None))
        )

        # result.all() returns list of Row objects — unpack as tuples
        return [(row.token, row.preferred_lang or "bn") for row in token_result.all()]

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
