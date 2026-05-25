from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
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
    summary="Register a new seeker account"
)
async def register_seeker(
    data: SeekerRegisterSchema,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    device_info: str | None = Depends(get_device_info),
):
    try:
        return await AuthService.register_seeker(data=data, db=db, response=response, device_info=device_info)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Seeker registration failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed. Please try again.",
        )


@router.post(
    "/register/provider",
    response_model=AuthResponseSchema,
    summary="Register a new provider account(Transaction = user + profile)"
)
async def register_provider(
    data: ProviderRegisterSchema,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    device_info: str | None = Depends(get_device_info),
):
    try:
        return await AuthService.register_provider(
            data=data, db=db, response=response, device_info=device_info)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Provider registration failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed. Please try again.",
        )
