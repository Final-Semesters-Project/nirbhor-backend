from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.i18n import t
from app.models.user_model import Role, User
from app.repositories.provider_repository import ProviderRepository
from app.schemas.user_schema import ProviderMeSchema, SeekerMeSchema


class UserService:

    @staticmethod
    async def get_me(
        current_user: User,
        db: AsyncSession,
        lang: str
    ) -> SeekerMeSchema | ProviderMeSchema:
        # Dynamically select the localized name variant
        localized_name = current_user.name_bn if lang == "bn" else current_user.name_en

        if current_user.role == Role.SEEKER:
            return SeekerMeSchema(
                user_id=current_user.id,
                role=current_user.role,
                phone=current_user.phone_en,
                name=localized_name,
                is_active=current_user.is_active,
                created_at=current_user.created_at
            )

        elif current_user.role == Role.PROVIDER:
            # fetch additional provider data from provider profile
            provider_repo = ProviderRepository(db)

            profile = await provider_repo.provider_profile_data_for_get_me(current_user.id)

            if profile is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=t("user_not_found", lang),
                )

            # Dynamically select the localized AI summary variant
            localized_summary = profile.ai_review_summary_bn if lang == "bn" else profile.ai_review_summary_en

            return ProviderMeSchema(
                user_id=current_user.id,
                role=current_user.role,
                phone=current_user.phone_en,
                name=localized_name,
                is_active=current_user.is_active,
                verification_level=profile.verification_level,
                verification_status=profile.verification_status,
                working_radius_km=profile.working_radius_km,
                has_smartphone=profile.has_smartphone,
                is_available=profile.is_available,
                average_rating=profile.average_rating,
                photo_url=profile.photo_url,
                nid_url_front=profile.nid_url_front,
                nid_url_back=profile.nid_url_back,
                warning_status=profile.warning_status,
                ai_review_summary=localized_summary,
                created_at=current_user.created_at,
                verification_rejection_reason=profile.verification_rejection_reason
            )

         # admin
        return SeekerMeSchema(
            user_id=current_user.id,
            role=current_user.role,
            phone=current_user.phone_en,
            name=localized_name,
            is_active=current_user.is_active,
            created_at=current_user.created_at
        )
