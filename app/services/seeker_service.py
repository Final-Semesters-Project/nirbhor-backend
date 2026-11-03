from uuid import UUID
from asyncpg import ForeignKeyViolationError, UniqueViolationError
from fastapi import HTTPException, status
from loguru import logger
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.cloudinary_helpers import delete_image_from_cloudinary
from app.core.exceptions import DomainIntegrityError, DomainValidationError
from app.core.geo import to_lat_lng
from app.core.i18n import t
from app.core.integrity_error_parser import parse_integrity_error
from app.repositories.seeker_repository import SeekerRepository
from app.repositories.user_repository import UserRepository
from app.schemas.seeker_schema import SeekerAddressUpdateSchema, SeekerAddressResponse, SeekerProfileUpdateSchema


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

    @staticmethod
    async def update_seeker_profile(
        seeker_id: UUID,
        db: AsyncSession,
        lang: str,
        update_data: SeekerProfileUpdateSchema,
    ) -> dict:
        seeker_repo = SeekerRepository(db)
        user_repo = UserRepository(db)

        # Prepare the update dictionary from the Pydantic model
        # Use exclude_unset=True for PATCH-style partial updates
        data_dict = update_data.model_dump(exclude_unset=True)

        user_data = {
            key: value
            for key, value in data_dict.items()
            if key in {"name_en", "name_bn"}
        }

        profile_data = {
            key: value
            for key, value in data_dict.items()
            if key in {"photo_public_id", "photo_url"}
        }

        user_instance = await user_repo.get_by_id(seeker_id)

        if user_instance is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=t("user_not_found", lang),
            )

        # fetch the existing seeker data
        seeker_instance = await seeker_repo.get_by_id(seeker_id)
        if seeker_instance is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=t("user_not_found", lang),
            )
        old_photo_public_id = seeker_instance.photo_public_id

        try:
            await user_repo.update(instance=user_instance, **user_data)
            await seeker_repo.update(instance=seeker_instance, **profile_data)

            await db.commit()

            await SeekerService._delete_old_image_if_changed(
                data_dict=data_dict,
                field_name="photo_public_id",
                current_value=old_photo_public_id,
            )

            return {
                "message": t("profile_updated", lang)
            }
        except IntegrityError as e:
            await db.rollback()
            raw = str(e.orig) if e.orig else str(e)
            readable = parse_integrity_error(raw, lang)

            # e.orig may be a string (SQLAlchemy asyncpg dialect behaviour) or
            # the actual asyncpg exception — handle both cases
            is_fk = (
                isinstance(e.orig, ForeignKeyViolationError)
                or "ForeignKeyViolationError" in raw
            )
            is_unique = (
                isinstance(e.orig, UniqueViolationError)
                or "UniqueViolationError" in raw
            )

            # unwrap the original asyncpg exception to route correctly
            if is_fk:
                logger.warning(
                    f"FK violation in provider profile update: {raw}")
                raise DomainValidationError(
                    error_message=readable,
                    raw_error=raw
                )
            if is_unique:
                logger.warning(
                    f"Unique violation in provider profile update: {raw}")
                raise DomainIntegrityError(
                    error_message=readable,
                    raw_error=raw
                )

            logger.error(f"IntegrityError in provider profile update: {raw}")
            raise DomainIntegrityError(error_message=readable, raw_error=raw)
        except (DomainIntegrityError, DomainValidationError):
            # let domain exceptions bubble up untouched to the global handler
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"Unexpected error in provider profile update: {e}")
            raise

    @staticmethod
    async def _delete_old_image_if_changed(
            data_dict: dict,
            field_name: str,
            current_value: str | None) -> None:
        """Delete old image from Cloudinary if a new value is provided."""
        if field_name in data_dict and current_value is not None:
            new_value = data_dict[field_name]
            if new_value != current_value:
                await delete_image_from_cloudinary(
                    public_id=current_value
                )
