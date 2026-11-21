from uuid import UUID
from app.models.seeker_profile_model import SeekerProfile
from app.repositories.base_repository import BaseRepository
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2.functions import ST_MakePoint, ST_SetSRID


class SeekerRepository(BaseRepository[SeekerProfile]):
    def __init__(self, db: AsyncSession):
        super().__init__(SeekerProfile, db)

    async def create_profile(
        self,
        user_id: UUID,
        latitude: float,
        longitude: float,
        home_address: str,
    ) -> SeekerProfile:
        # WKT (Well-Known Text) format for PostGIS point
        # POINT(longitude latitude) — note: longitude first, this is the GIS standard
        # location_wkt = f"POINT({longitude} {latitude})"

        point = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)

        profile = SeekerProfile(
            user_id=user_id, home_address=home_address, home_location=point
        )
        self.db.add(profile)
        await self.db.flush()
        return profile

    async def seeker_profile_data_for_get_me(self, user_id: UUID):
        return await self.db.get(SeekerProfile, user_id)

    async def update_address(
        self, user_id: UUID, latitude: float, longitude: float, address: str
    ) -> SeekerProfile:
        """Update if the row exists, create it otherwise (legacy seekers)."""
        profile = await self.seeker_profile_data_for_get_me(user_id)

        if profile is None:
            return await self.create_profile(
                user_id=user_id,
                latitude=latitude,
                longitude=longitude,
                home_address=address,
            )

        profile.home_location = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
        profile.home_address = address
        await self.db.flush()
        return profile
