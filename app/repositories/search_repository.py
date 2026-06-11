from uuid import UUID

from geoalchemy2 import Geography
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func, case, text
from geoalchemy2.functions import ST_DWithin, ST_Distance, ST_MakePoint, ST_SetSRID
from app.models.provider_profile_model import ProviderProfile, VerificationLevel
from app.models.provider_skill_link_model import ProviderSkillLink
from app.models.skill_model import Skill
from app.models.user_model import User


class SearchRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def find_providers(
        self,
        skill_id: int,
        seeker_lat: float,
        seeker_lng: float,
        search_radius_km: int,
    ) -> list[dict]:
        """
        Core geospatial search with inline ranking score.

        Score formula (from spec):
            score = (1/distance_km)
                  + (average_rating * 2)
                  + verification_bonus   [TRUSTED=+5, VERIFIED=+3, else 0]
                  + activity_bonus       [0-3d=+10, 4-15d=+5, 16-30d=-30, 31-60d=-60]
                  + (recent_booking_count * 0.5)

        Filters:
            - provider must have a skill in the requested category
            - provider base_location must be within search_radius_km of seeker
            - is_available must be True
            - last_active_at must not be older than 60 days
        """
        now = datetime.now(timezone.utc)

        # Convert KM to meters for ST_DWithin (geography uses meters)
        radius_m = search_radius_km * 1000

        seeker_point = ST_SetSRID(ST_MakePoint(seeker_lng, seeker_lat), 4326)

        # ── Days since provider was last active ───────────────────────────────
        # func.extract("epoch", interval) converts a time difference to seconds
        # days_inactive: a float like 2.5 (days)
        days_inactive = func.extract(
            "epoch",
            now - User.last_active_at
        ) / 86400  # convert seconds to days

        # ── Activity bonus/penalty as a CASE expression ───────────────────────
        # case() works like SQL CASE WHEN ... THEN ... END
        # SQLAlchemy evaluates conditions top to bottom, first match wins
        activity_score = case(
            (days_inactive <= 3,  10.0),
            (days_inactive <= 15,  5.0),
            (days_inactive <= 30, -30.0),
            (days_inactive <= 60, -60.0),
            else_=-60.0,  # fallback (shouldn't reach here due to WHERE filter)
        )

        # ── Verification bonus ────────────────────────────────────────────────
        verification_score = case(
            (ProviderProfile.verification_level == VerificationLevel.TRUSTED,  5.0),
            (ProviderProfile.verification_level == VerificationLevel.VERIFIED, 3.0),
            else_=0.0,
        )

        # ── Distance in KM from seeker to provider base_location ─────────────
        # .cast(Geography) tells PostGIS to treat the geometry as a geographic
        # object so ST_Distance returns meters (not degrees).
        # ST_Distance with geography=True returns meters
        distance_m = ST_Distance(
            ProviderProfile.base_location.cast(Geography),
            seeker_point.cast(Geography)
        )
        distance_km = distance_m / 1000.0

        # ── Recent completed bookings (last 30 days) ───────────────────────────────
        # Subquery: how many completed bookings has this provider had?
        # scalar_subquery() runs one SELECT per provider row to count their
        # recent completions. correlate(ProviderProfile) tells SQLAlchemy this
        # subquery links to the outer query's ProviderProfile rows.
        from app.models.booking_model import Booking, BookingStatus
        recent_bookings_sq = (
            select(func.count())
            .where(Booking.provider_id == ProviderProfile.user_id)
            .where(Booking.status == BookingStatus.COMPLETED)
            .where(Booking.completed_at >= now - timedelta(days=30))
            .correlate(ProviderProfile)
            .scalar_subquery()
        )

        # ── Composite ranking score ───────────────────────────────────────────
        # func.nullif(distance_km, 0) returns NULL if distance_km is 0.
        # This prevents division-by-zero when provider is at the exact same
        # point as the seeker. NULL propagates through arithmetic so the
        # whole score becomes NULL instead of crashing — and NULL rows sort
        # last, which is acceptable (a provider at distance=0 is likely a
        # test/bad data row anyway).
        ranking_score = (
            (1.0 / func.nullif(distance_km, 0))
            + (func.coalesce(ProviderProfile.average_rating, 0.0) * 2.0)
            + verification_score
            + activity_score
            + (recent_bookings_sq * 0.5)
        )

        stmt = (
            select(
                User.id.label("user_id"),
                User.last_active_at,
                ProviderProfile.working_radius_km,
                ProviderProfile.verification_level,
                ProviderProfile.average_rating,
                ProviderProfile.has_smartphone,
                ProviderProfile.is_available,
                distance_km.label("distance_km"),
                ranking_score.label("score"),
            )
            .join(ProviderProfile, User.id == ProviderProfile.user_id)
            .join(ProviderSkillLink, ProviderProfile.user_id == ProviderSkillLink.provider_id)
            # ── Filters ───────────────────────────────────────────────────────
            .where(ProviderSkillLink.skill_id == skill_id)
            .where(ProviderProfile.is_available == True)
            .where(User.is_active == True)
            # provider working radius must overlap seeker location
            # ST_DWithin uses the spatial index — fast.
            # Checks if provider's base_location is within radius_m of seeker
            .where(
                ST_DWithin(
                    ProviderProfile.base_location.cast(Geography),
                    seeker_point.cast(Geography),
                    radius_m,
                )
            )
            # exclude 60+ day inactive providers entirely
            .where(
                User.last_active_at >= now - timedelta(days=60)
            )
            # ── distinct(User.id) ─────────────────────────────────────────────
            # A provider can have multiple skills. Without distinct, a provider
            # with 3 skills in the same category would appear 3 times in results.
            # distinct(User.id) keeps only one row per provider.
            # PostgreSQL requires the distinct column to appear first in ORDER BY,
            # so we order by User.id first, then ranking_score.
            .distinct(User.id)
            .order_by(ranking_score.desc())
        )

        result = await self.db.execute(stmt)
        return [dict(row._mapping) for row in result.all()]

    async def get_provider_names(
        self, provider_ids: list[UUID], lang: str
    ) -> dict[UUID, str]:
        if not provider_ids:
            return {}
        name_col = func.coalesce(User.name_bn, User.name_en).label("name") \
            if lang == "bn" else User.name_en.label("name")
        result = await self.db.execute(
            select(User.id, name_col).where(User.id.in_(provider_ids))
        )
        return {row.id: row.name for row in result.all()}

    async def get_provider_skill_names(
        self, provider_ids: list[UUID], skill_id: int, lang: str
    ) -> dict[UUID, list[str]]:
        """
        For the given skill_id, fetch its name once and return it for all
        providers. A single skill search means all providers share the same
        skill name — no need to query per provider.
        """
        if not provider_ids:
            return {}
        name_col = Skill.name_bn if lang == "bn" else Skill.name_en
        result = await self.db.execute(
            select(name_col).where(Skill.id == skill_id)
        )
        skill_name = result.scalar_one_or_none() or ""
        # Every provider in results has this skill
        return {pid: [skill_name] for pid in provider_ids}
