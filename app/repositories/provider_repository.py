from uuid import UUID
from sqlalchemy import select, func, and_, delete
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.booking_model import Booking
from app.models.provider_profile_model import ProviderProfile
from app.models.provider_skill_link_model import ProviderSkillLink
from app.models.user_model import User
from app.repositories.base_repository import BaseRepository
from geoalchemy2.functions import ST_MakePoint, ST_SetSRID


class ProviderRepository(BaseRepository[ProviderProfile]):
    def __init__(self, db: AsyncSession):
        super().__init__(ProviderProfile, db)

    async def create_profile(
        self,
        user_id: UUID,
        latitude: float,
        longitude: float,
        working_radius_km: int,
        has_smartphone: bool
    ) -> ProviderProfile:
        # WKT (Well-Known Text) format for PostGIS point
        # POINT(longitude latitude) — note: longitude first, this is the GIS standard
        # location_wkt = f"POINT({longitude} {latitude})"

        point = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)

        profile = ProviderProfile(
            user_id=user_id,
            base_location=point,
            working_radius_km=working_radius_km,
            has_smartphone=has_smartphone,
            location_updated_at=func.now(),
            radius_updated_at=func.now(),
        )
        self.db.add(profile)
        await self.db.flush()
        return profile

    async def add_skills(
        self, provider_id: UUID, skill_ids: list[int]
    ) -> None:
        for skill_id in skill_ids:
            link = ProviderSkillLink(
                provider_id=provider_id,
                skill_id=skill_id,
            )
            self.db.add(link)
        await self.db.flush()

    async def provider_profile_data_for_get_me(self, user_id: UUID):
        return await self.db.get(ProviderProfile, user_id)

    async def get_dashboard_data(self, user_id: UUID):
        query = select(ProviderProfile)\
            .options(
                joinedload(ProviderProfile.user),
                joinedload(ProviderProfile.skill_links).joinedload(
                    ProviderSkillLink.skill),
        ).where(ProviderProfile.user_id == user_id)

        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_total_jobs_done(self, user_id: UUID):
        # count total jobs done by provider from bookings table where status is completed
        query = select(func.count(Booking.id)).where(
            and_(
                Booking.provider_id == user_id,
                Booking.status == "completed"
            )
        )

        result = await self.db.execute(query)
        return result.scalar()

    async def get_public_profile(
        self, provider_id: UUID, lang: str
    ) -> dict | None:
        """
        Fetch everything needed for a provider's public profile card.
        Returns None if provider does not exist or is not active.
        """
        from app.models.skill_model import Skill
        from app.models.provider_skill_link_model import ProviderSkillLink
        from sqlalchemy import func

        # Fetch user + profile in one join
        result = await self.db.execute(
            select(User, ProviderProfile)
            .join(ProviderProfile, User.id == ProviderProfile.user_id)
            .where(User.id == provider_id)
            .where(User.is_active == True)
        )
        row = result.first()
        if not row:
            return None

        user, profile = row

        # Fetch skills with localized names
        name_col = Skill.name_bn if lang == "bn" else Skill.name_en
        skills_result = await self.db.execute(
            select(Skill.id, name_col.label("name"))
            .join(ProviderSkillLink, Skill.id == ProviderSkillLink.skill_id)
            .where(ProviderSkillLink.provider_id == provider_id)
        )
        skills = [{"id": r.id, "name": r.name} for r in skills_result.all()]

        # Localized name and AI summary
        name = user.name_bn if lang == "bn" else user.name_en

        ai_summary = profile.ai_review_summary_bn if lang == "bn" else profile.ai_review_summary_en

        return {
            "user_id": user.id,
            "name": name,
            "photo_url": profile.photo_url,
            "verification_level": profile.verification_level.value,
            "average_rating": profile.average_rating,
            "working_radius_km": profile.working_radius_km,
            "has_smartphone": profile.has_smartphone,
            "is_available": profile.is_available,
            "ai_review_summary": ai_summary,
            "skills": skills,
            "last_active_at": user.last_active_at,
        }
