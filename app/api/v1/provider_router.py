from fastapi import APIRouter, Depends, HTTPException, Header, status, Response, Request
from loguru import logger
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import get_current_provider
from app.core.exceptions import DomainIntegrityError
from app.core.i18n import MESSAGES, get_lang, t
from app.db.session import get_db_session
from app.models.user_model import User
from app.schemas.provider_schema import ProviderProfileUpdateSchema, AddNewSkillSchema
from app.services.provider_service import ProviderService

router = APIRouter(prefix="/provider", tags=["Provider Management"])


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
