import uuid
from sqlalchemy import select, func, and_
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.booking_model import Booking
from app.models.provider_profile_model import ProviderProfile
from app.models.provider_skill_link_model import ProviderSkillLink
from app.repositories.base_repository import BaseRepository
from geoalchemy2.functions import ST_MakePoint, ST_SetSRID


class ProviderRepository(BaseRepository[ProviderProfile]):
    def __init__(self, db: AsyncSession):
        super().__init__(ProviderProfile, db)

    async def create_profile(
        self,
        user_id: uuid.UUID,
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
        self, provider_id: uuid.UUID, skill_ids: list[int]
    ) -> None:
        for skill_id in skill_ids:
            link = ProviderSkillLink(
                provider_id=provider_id,
                skill_id=skill_id,
            )
            self.db.add(link)
        await self.db.flush()

    async def provider_profile_data_for_get_me(self, user_id: uuid.UUID):
        return await self.db.get(ProviderProfile, user_id)

    async def get_dashboard_data(self, user_id: uuid.UUID):
        query = select(ProviderProfile)\
            .options(
                joinedload(ProviderProfile.user),
                joinedload(ProviderProfile.skill_links).joinedload(
                    ProviderSkillLink.skill),
        ).where(ProviderProfile.user_id == user_id)

        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_total_jobs_done(self, user_id: uuid.UUID):
        # count total jobs done by provider from bookings table where status is completed
        query = select(func.count(Booking.id)).where(
            and_(
                Booking.provider_id == user_id,
                Booking.status == "completed"
            )
        )

        result = await self.db.execute(query)
        return result.scalar()
