from loguru import logger
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import DomainIntegrityError
from app.core.i18n import t
from app.core.integrity_error_parser import parse_integrity_error
from app.models.category_model import Category
from app.models.skill_model import Skill
from app.models.user_model import User
from app.repositories.provider_repository import ProviderRepository
from app.repositories.skill_repository import SkillRepository
from fastapi import HTTPException, status
from app.schemas.provider_schema import ProviderDashboardSchema, SkillInfo


class ProviderService:
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
