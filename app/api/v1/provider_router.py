from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import get_current_provider, get_current_seeker
from app.core.i18n import get_lang
from app.db.session import get_db_session
from app.models.user_model import User
from app.schemas.provider_schema import ProviderProfileUpdateSchema, AddNewSkillSchema, PublicProviderProfile
from app.services.provider_service import ProviderService

router = APIRouter(prefix="/provider", tags=["Provider Management"])


# for provider dashboard page: 1 api to get a list of skills and 1 to add that skill to provider
@router.post(
    "/me/add_skill",
    summary="Add skill to provider",
    status_code=status.HTTP_200_OK,
    response_model=dict
)
async def add_skills(
    payload: AddNewSkillSchema,
    current_user: User = Depends(get_current_provider),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    return await ProviderService.add_new_skills(db=db, lang=lang, provider_id=current_user.id, payload=payload)

# Provider dashboard data


@router.get(
    "/dashboard",
    summary="Get provider dashboard data",
    status_code=status.HTTP_200_OK
)
async def get_provider_dashboard(
    current_user: User = Depends(get_current_provider),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    return await ProviderService.get_dashboard(current_user=current_user, db=db, lang=lang)


@router.get("/{provider_id}/public", response_model=PublicProviderProfile)
async def get_provider_public_profile(
    provider_id: UUID,
    current_user: User = Depends(get_current_seeker),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """
    Seeker taps a provider card to see their full public profile.
    Phone is NOT included — only revealed after booking initiation.
    """
    return await ProviderService.get_public_profile(
        provider_id=provider_id,
        db=db,
        lang=lang,
    )


@router.patch(
    "/me/update_profile",
    summary="Update provider profile",
    status_code=status.HTTP_200_OK,
    response_model=dict
)
async def update_provider_profile(
    update_data: ProviderProfileUpdateSchema,
    current_user: User = Depends(get_current_provider),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    return await ProviderService.update_provider_profile(db=db, lang=lang, provider_id=current_user.id, update_data=update_data)


# remove a linked skill from the provider profile
@router.delete(
    "/me/remove_skill",
    summary="Remove a linked skill from provider profile",
    status_code=status.HTTP_200_OK,
    response_model=dict
)
async def remove_a_skill(
    skill_id: int,
    current_user: User = Depends(get_current_provider),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    return await ProviderService.delete_providers_skill(
        db=db, lang=lang, provider_id=current_user.id, skill_id=skill_id)
