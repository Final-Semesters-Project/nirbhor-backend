import uuid
from datetime import datetime, timezone

from asyncpg import ForeignKeyViolationError, UniqueViolationError
from loguru import logger
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import DomainIntegrityError, DomainValidationError
from app.core.i18n import t
from app.core.integrity_error_parser import parse_integrity_error
from app.models.category_model import Category
from app.models.provider_profile_model import ProviderProfile
from app.models.skill_model import Skill
from app.models.user_model import User
from app.repositories.provider_repository import ProviderRepository
from app.repositories.skill_repository import SkillRepository
from fastapi import HTTPException, status
from app.schemas.provider_schema import AddNewSkillSchema, ProviderDashboardSchema, ProviderProfileUpdateSchema, SkillInfo
from app.services.cloudinary_service import delete_image_from_cloudinary


class ProviderService:

    @staticmethod
    async def _delete_old_image_if_changed(data_dict: dict, field_name: str, current_value: str | None) -> None:
        """Delete old image from Cloudinary if a new value is provided."""
        if field_name in data_dict and current_value is not None:
            new_value = data_dict[field_name]
            if new_value != current_value:
                await delete_image_from_cloudinary(public_id=current_value)

    @staticmethod
    async def get_dashboard(
        current_user: User,
        db: AsyncSession,
        lang: str
    ):
        # Dynamically select the localized name variant
        localized_name = current_user.name_bn if lang == "bn" else current_user.name_en

        # create provider, user instance
        provider_repo = ProviderRepository(db)

        # get provider data
        provider = await provider_repo.get_dashboard_data(current_user.id)

        if provider is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=t("user_not_found", lang),
            )
        logger.info(f"Provider: {provider}")
        # Dynamically select the localized AI summary variant
        localized_summary = provider.ai_review_summary_bn if lang == "bn" else provider.ai_review_summary_en

        # calculate total jobs done
        total_jobs_done = await provider_repo.get_total_jobs_done(current_user.id)

        return ProviderDashboardSchema(
            user_id=current_user.id,
            name=localized_name,
            photo_url=provider.photo_url,
            is_available=provider.is_available,
            verification_level=provider.verification_level,
            average_rating=provider.average_rating,
            ai_review_summary=localized_summary,
            working_radius_km=provider.working_radius_km,
            skills=[
                SkillInfo(
                    id=link.skill.id,
                    name=link.skill.name_bn if lang == "bn" else link.skill.name_en
                )
                for link in provider.skill_links
            ],
            total_jobs_done=total_jobs_done
        )

    @staticmethod
    async def update_provider_profile(
        provider_id: uuid.UUID,
        lang: str,
        db: AsyncSession,
        update_data: ProviderProfileUpdateSchema
    ) -> dict:
        # re-validate with language context so error messages are translated
        data = ProviderProfileUpdateSchema.model_validate(
            update_data.model_dump(),
            context={"lang": lang}
        )

        provider_repo = ProviderRepository(db)

        # fetch the existing provider data
        provider_instance = await provider_repo.get_by_id(provider_id)
        if provider_instance is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=t("user_not_found", lang),
            )

        # Prepare the update dictionary from the Pydantic model
        # Use exclude_unset=True for PATCH-style partial updates
        data_dict = update_data.model_dump(exclude_unset=True)

        # handle location logic and update the data_dict
        if "latitude" in data_dict and "longitude" in data_dict:
            days_difference = (datetime.now(timezone.utc) -
                               provider_instance.location_updated_at).days

            if days_difference < 7:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=t("location_update_limit", lang),
                )
            data_dict["base_location"] = f"POINT({data_dict["longitude"]} {data_dict["latitude"]})"
            data_dict["location_updated_at"] = func.now()

        if "working_radius_km" in data_dict:
            days_difference = (datetime.now(timezone.utc) -
                               provider_instance.radius_updated_at).days

            if days_difference < 7:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=t("radius_update_limit", lang),
                )

            data_dict["radius_updated_at"] = func.now()

        # if "photo_public_id" in data_dict and provider_instance.photo_public_id is not None:
        #     if data_dict["photo_public_id"] != provider_instance.photo_public_id:
        #         await delete_image_from_cloudinary(public_id=provider_instance.photo_public_id)

        # if "nid_front_public_id" in data_dict and provider_instance.nid_front_public_id is not None:
        #     if data_dict["nid_front_public_id"] != provider_instance.nid_front_public_id:
        #         await delete_image_from_cloudinary(public_id=provider_instance.nid_front_public_id)

        # if "nid_back_public_id" in data_dict and provider_instance.nid_back_public_id is not None:
        #     if data_dict["nid_back_public_id"] != provider_instance.nid_back_public_id:
        #         await delete_image_from_cloudinary(public_id=provider_instance.nid_back_public_id)

        # handling images = new photo uploaded in cloudinary -> client send url + public_id -> delete the old photo from cloudinary -> update the photo url and public_id
        await ProviderService._delete_old_image_if_changed(data_dict, "photo_public_id", provider_instance.photo_public_id)
        await ProviderService._delete_old_image_if_changed(data_dict, "nid_front_public_id", provider_instance.nid_front_public_id)
        await ProviderService._delete_old_image_if_changed(data_dict, "nid_back_public_id", provider_instance.nid_back_public_id)

        try:
            await provider_repo.update(instance=provider_instance, **data_dict)
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
    async def add_new_skills(
        provider_id: uuid.UUID,
        payload: AddNewSkillSchema,
        db: AsyncSession,
        lang: str
    ) -> dict:

        try:
            provider_repo = ProviderRepository(db)

            provider = await provider_repo.get_by_id(provider_id)

            if provider is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=t("user_not_found", lang),
                )

            if len(payload.skill_ids) == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=t("empty_data", lang),
                )

            await provider_repo.add_skills(provider_id=provider_id, skill_ids=payload.skill_ids)

            await db.commit()
            logger.success("New skill added successfully to provider")

            return {
                "message": t("new_skill_added", lang)
            }
        except IntegrityError as e:
            await db.rollback()
            raw = str(e.orig) if e.orig else str(e)
            # translates according to lang
            readable = parse_integrity_error(raw, lang)

            # e.orig may be a string (SQLAlchemy asyncpg dialect behavior) or
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
                    f"FK violation in adding new skill to provider: {raw}")
                raise DomainValidationError(
                    error_message=readable,
                    raw_error=raw
                )
            if is_unique:
                logger.warning(
                    f"Unique violation in adding new skill to provider: {raw}")
                raise DomainIntegrityError(
                    error_message=readable,
                    raw_error=raw
                )
            logger.error(
                f"IntegrityError in adding new skill to provider: {raw}")
            raise DomainIntegrityError(error_message=readable, raw_error=raw)
        except (DomainIntegrityError, DomainValidationError):
            # let domain exceptions bubble up untouched to the global handler
            raise
        except Exception as e:
            await db.rollback()
            logger.error(
                f"Unexpected error in adding new skill to provider: {e}")
            raise
