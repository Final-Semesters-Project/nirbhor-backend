from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import get_current_user
from app.core.i18n import get_lang, t
from app.db.session import get_db_session
from app.models.user_model import User
from app.schemas.user_schema import SeekerMeSchema, ProviderMeSchema
from app.services.user_service import UserService
from loguru import logger

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/me",
    summary="Get current user profile",
    response_model=SeekerMeSchema | ProviderMeSchema,
    status_code=status.HTTP_200_OK,
)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
) -> SeekerMeSchema | ProviderMeSchema:
    try:
        return await UserService.get_me(current_user, db, lang)
    except Exception as e:
        logger.critical(f"Failed to get current user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=t("user_not_found", lang),
        )
