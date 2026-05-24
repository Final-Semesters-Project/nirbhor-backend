```
POST /api/v1/auth/register/seeker    ← name, phone, password
POST /api/v1/auth/register/provider  ← name, phone, password, skills, location, radius, has_smartphone
```

# app/repositories/provider_repository.py
```python
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.provider_profile_model import ProviderProfile
from app.models.provider_skills_link_model import ProviderSkillsLink
from app.repositories.base import BaseRepository


class ProviderRepository(BaseRepository[ProviderProfile]):
    def __init__(self, db: AsyncSession):
        super().__init__(ProviderProfile, db)

    async def create_profile(
        self,
        user_id: uuid.UUID,
        name_en: str,
        latitude: float,
        longitude: float,
        working_radius_km: int,
        has_smartphone: bool,
    ) -> ProviderProfile:
        # WKT (Well-Known Text) format for PostGIS point
        # POINT(longitude latitude) — note: longitude first, this is the GIS standard
        location_wkt = f"POINT({longitude} {latitude})"

        profile = ProviderProfile(
            user_id=user_id,
            name_en=name_en,
            base_location=location_wkt,
            working_radius_km=working_radius_km,
            has_smartphone=has_smartphone,
        )
        self.db.add(profile)
        await self.db.flush()
        return profile

    async def add_skills(
        self, provider_id: uuid.UUID, skill_ids: list[int]
    ) -> None:
        for skill_id in skill_ids:
            link = ProviderSkillsLink(
                provider_id=provider_id,
                skill_id=skill_id,
            )
            self.db.add(link)
        await self.db.flush()
```
