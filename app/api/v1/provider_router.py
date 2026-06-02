from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Header, status, Response, Request
from loguru import logger
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import get_current_provider
from app.core.exceptions import DomainIntegrityError
from app.core.i18n import MESSAGES, get_lang, t
from app.db.session import get_db_session
from app.models.user_model import User
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
    try:
        return await ProviderService.get_dashboard(current_user=current_user, db=db, lang=lang)
    except ValidationError as ve:
        logger.critical(f"Validation error: {ve}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {ve}",
        )
    except Exception as e:
        logger.critical(f"Failed to get provider dashboard: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=t("user_not_found", lang),
        )
