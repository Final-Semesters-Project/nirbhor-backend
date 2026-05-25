import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.provider_profile_model import ProviderProfile
from app.models.provider_skill_link_model import ProviderSkillLink
from app.repositories.base_repository import BaseRepository


class ProviderRepository(BaseRepository[ProviderProfile]):
    def __init__(self, db: AsyncSession):
        super().__init__(ProviderProfile, db)

    async def create_profile(
        self,
        user_id: uuid.UUID,
        name_en: str,
        name_bn: str,
        latitude: float,
        longitude: float,
        working_radius_km: int,
        has_smartphone: bool,
        photo_url: str | None = None,
        nid_url: str | None = None,
    ) -> ProviderProfile:
        # WKT (Well-Known Text) format for PostGIS point
        # POINT(longitude latitude) — note: longitude first, this is the GIS standard
        location_wkt = f"POINT({longitude} {latitude})"

        profile = ProviderProfile(
            user_id=user_id,
            name_en=name_en,
            name_bn=name_bn,
            base_location=location_wkt,
            working_radius_km=working_radius_km,
            has_smartphone=has_smartphone,
            photo_url=photo_url,
            nid_url=nid_url,
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
