from fastapi import APIRouter, Depends, Header, status, Response, Request
from fastapi.security import OAuth2PasswordRequestForm
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.api.dependencies import get_current_seeker, get_current_provider, get_current_user
from app.core.i18n import get_lang
from app.db.session import get_db_session
from app.models.user_model import User
from app.schemas.auth_schema import (
    FCMTokenRequest,
    LogoutSchema,
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
    return await AuthService.register_seeker(data=data, db=db, response=response, device_info=device_info, lang=lang)


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

    return await AuthService.register_provider(
        data=data, db=db, response=response, device_info=device_info, lang=lang)


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
    return await AuthService.password_login(response=response, username=form_data.username, password=form_data.password, db=db, device_info=device_info, lang=lang)


@router.post("/fcm/token", status_code=201)
async def register_fcm_token(
    data: FCMTokenRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Called by Flutter/React after login to register the device FCM token."""

    return await AuthService.register_fcm_token(
        user_id=current_user.id,
        token=data.token,
        device_type=data.device_type,
        db=db,
    )


@router.post("/logout", status_code=200)
async def logout(
    data: LogoutSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
    authorization: str = Header(...),
):
    """
    Logs out the current device:
    - Deletes the refresh token session (other devices stay logged in)
    - Blocklists the current access token until it naturally expires
    - Optionally removes this device's FCM token
    """
    access_token = authorization.replace("Bearer ", "")
    return await AuthService.logout(
        data=data,
        access_token=access_token,
        user_id=current_user.id,
        db=db,
        lang=lang,
    )
