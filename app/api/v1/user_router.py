from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import get_current_user
from app.core.i18n import get_lang, t
from app.db.session import get_db_session
from app.models.user_model import User
from app.schemas.user_schema import AdminMeSchema, PreferredLanguageToggleSchema, SeekerMeSchema, ProviderMeSchema, UpdatePasswordSchema
from app.services.user_service import UserService
from loguru import logger

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/me",
    summary="Get current user profile",
    response_model=SeekerMeSchema | ProviderMeSchema | AdminMeSchema,
    status_code=status.HTTP_200_OK,
)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
) -> SeekerMeSchema | ProviderMeSchema | AdminMeSchema:
    return await UserService.get_me(current_user, db, lang)


@router.patch(
    '/me/update-password',
    summary="Update password",
    status_code=status.HTTP_200_OK,
)
async def update_password(
    data: UpdatePasswordSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    return await UserService.update_password(data=data, current_user=current_user, db=db, lang=lang)

# @router.patch(
#     "/me/toggle_preferred_language",
#     summary="Toggle preferred language",
#     status_code=status.HTTP_200_OK,
# )
# async def toggle_preferred_language(
#     data: PreferredLanguageToggleSchema,
#     current_user: User = Depends(get_current_user),
#     db: AsyncSession = Depends(get_db_session),
#     lang: str = Depends(get_lang),
# ):
#     return await UserService.toggle_preferred_language(
#         data=data, current_user=current_user, db=db, lang=lang)
