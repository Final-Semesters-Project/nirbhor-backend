from fastapi import APIRouter, Depends, HTTPException, status, Response
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


@router.post(
    "/register/seeker",
    response_model=AuthResponseSchema,
    summary="Register a new seeker account",
)
async def register_seeker(
    data: SeekerRegisterSchema,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
):
    try:
        return await AuthService.register_seeker(data=data, db=db, response=response, device_info=None)
    except Exception as e:
        logger.error(f"Seeker registration failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed. Please try again.",
        )
