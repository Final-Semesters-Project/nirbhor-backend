from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import OAuth2PasswordRequestForm
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import DomainIntegrityError
from app.core.i18n import MESSAGES, get_lang, t, make_validated_body
from app.db.session import get_db_session
from app.schemas.auth_schema import (
    SeekerRegisterSchema,
    ProviderRegisterSchema,
    AuthResponseSchema,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


# Extract device info from User-Agent header for session tracking
def get_device_info(request: Request) -> str | None:
    return request.headers.get("User-Agent")


@router.post(
    "/register/seeker",
    response_model=AuthResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new seeker account"
)
async def register_seeker(
    response: Response,
    data: SeekerRegisterSchema,
    db: AsyncSession = Depends(get_db_session),
    device_info: str | None = Depends(get_device_info),
    lang: str = Depends(get_lang),
):
    try:
        return await AuthService.register_seeker(data=data, db=db, response=response, device_info=device_info, lang=lang)
    except HTTPException:
        raise
    except DomainIntegrityError as de:
        logger.error(
            f"Domain Integrity Error: Seeker registration failed: {de}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t("registration_failed", lang),
        )
    except Exception as e:
        logger.error(f"Seeker registration failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=t("registration_failed", lang),
        )


@router.post(
    "/register/provider",
    response_model=AuthResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new provider account(Transaction = user + profile)"
)
async def register_provider(
    response: Response,
    data: ProviderRegisterSchema,
    db: AsyncSession = Depends(get_db_session),
    device_info: str | None = Depends(get_device_info),
    lang: str = Depends(get_lang),
):
    try:
        return await AuthService.register_provider(
            data=data, db=db, response=response, device_info=device_info, lang=lang)
    except HTTPException:
        raise
    except DomainIntegrityError as de:
        logger.error(
            f"Domain Integrity Error: Provider registration failed: {de}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t("registration_failed", lang),
        )
    except Exception as e:
        logger.error(f"Provider registration failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=t("registration_failed", lang),
        )


# login route
@router.post(
    "/login",
    response_model=AuthResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Login with phone number and password",
)
async def password_login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db_session),
    device_info: str | None = Depends(get_device_info),
    lang: str = Depends(get_lang),
):
    try:
        return await AuthService.password_login(response=response, username=form_data.username, password=form_data.password, db=db, device_info=device_info, lang=lang)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password Login failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=t("login_failed", lang),
        )
