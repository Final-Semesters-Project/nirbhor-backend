from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.geo import to_lat_lng
from app.repositories.seeker_repository import SeekerRepository
from app.schemas.seeker_schema import SeekerAddressUpdateSchema, SeekerAddressResponse


class SeekerService:

    @staticmethod
    async def get_address(user_id: UUID, db: AsyncSession) -> SeekerAddressResponse:
        seeker_repo = SeekerRepository(db)

        profile = await seeker_repo.seeker_profile_data_for_get_me(user_id)

        if profile is None:
            return SeekerAddressResponse()  # 200 with nulls, not 404

        point = to_lat_lng(profile.home_location)

        if point is None:
            return SeekerAddressResponse()

        lat, lng = point

        return SeekerAddressResponse(
            latitude=lat, longitude=lng, home_address=profile.home_address
        )

    @staticmethod
    async def update_address(
        user_id: UUID, data: SeekerAddressUpdateSchema, db: AsyncSession
    ):
        seeker_repo = SeekerRepository(db)

        await seeker_repo.update_address(
            user_id=user_id,
            latitude=data.latitude,
            longitude=data.longitude,
            address=data.home_address,
        )
        await db.commit()

        # echo the input back: avoids re-reading a just-flushed geometry
        return {
            "message": "Address updated",
        }
