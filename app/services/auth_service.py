from fastapi import HTTPException, status, Response
from loguru import logger
from app.repositories.user_repository import UserRepository
from app.repositories.user_session_repository import UserSessionRepository
from app.schemas.auth_schema import AuthResponseSchema, ProviderRegisterSchema, SeekerRegisterSchema
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import Security
from app.models.user_model import Role
from datetime import timedelta
from app.core.config import settings
import uuid
from datetime import datetime, timezone


class AuthService:

    # private helper method to create, store and set tokens. Used by both register and login
    @staticmethod
    async def _create_tokens_and_session(
        user_id: uuid.UUID,
        role: str,
        response: Response,
        db: AsyncSession,
        device_info: str | None = None,
    ) -> AuthResponseSchema:
        # create access token
        access_token = Security.create_access_token(
            subject=str(user_id),
            role=role,
        )

        # create refresh token
        refresh_token = Security.create_refresh_token(
            subject=str(user_id),
        )

        # store refresh token in DB for validation and revocation
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES
        )

        session_repo = UserSessionRepository(db)
        await session_repo.create(
            user_id=user_id,
            refresh_token=refresh_token,
            device_info=device_info,
            expires_at=expires_at,
        )

        # set refresh token as HttpOnly cookie for browser
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=True,
            # samesite="lax" breaks cross-origin cookie sending from frontend to backend if deployed in separate platforms. eg: Vercel -> Render
            samesite="none",
            max_age=settings.REFRESH_TOKEN_EXPIRE_MINUTES * 60
        )

        # return tokens
        return AuthResponseSchema(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            role=role,
            user_id=user_id,
        )

    @staticmethod
    async def register_seeker(
        data: SeekerRegisterSchema,
        db: AsyncSession,
        response: Response,
        device_info: str | None = None,
    ) -> AuthResponseSchema:

        # Create an instance of UserRepository
        user_repo = UserRepository(db)

        # business rule: phone must be unique
        existing = await user_repo.get_by_phone(data.phone)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this phone number already exists",
            )

        try:
            # create user
            user = await user_repo.create(
                phone_en=data.phone,
                password_hash=Security.hash_password(data.password),
                role=Role.SEEKER,
            )

            # create and store tokens
            # Web → access token in response body + refresh token in HttpOnly cookie
            # Flutter → access token + refresh token in response body
            result = await AuthService._create_tokens_and_session(
                user_id=user.id,
                role=user.role.value,
                response=response,
                db=db,
                device_info=device_info,
            )

            await db.commit()
            # await db.refresh(user)

            logger.success(f"Seeker registered: {user.id}")
            return result
        except HTTPException:
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"Seeker registration failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Registration failed. Please try again.",
            )

    # register provider

    @staticmethod
    async def register_provider(
        data: ProviderRegisterSchema,
        db: AsyncSession,
        response: Response,
        device_info: str | None = None,
    ) -> AuthResponseSchema:

        # Create an instance of UserRepository
        user_repo = UserRepository(db)
        # provider_repo = ProviderRepository(db)

        # business rule: phone must be unique
        existing = await user_repo.get_by_phone(data.phone)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this phone number already exists",
            )

        try:
            # create user
            user = await user_repo.create(
                phone_en=data.phone,
                password_hash=Security.hash_password(data.password),
                role=Role.SEEKER,
            )

            # create and store tokens            # Web → access token in response body + refresh token in HttpOnly cookie
            # Flutter → access token + refresh token in response body
            result = await AuthService._create_tokens_and_session(
                user_id=user.id,
                role=user.role.value,
                response=response,
                db=db,
                device_info=device_info,
            )

            await db.commit()
            await db.refresh(user)

            logger.success(f"Seeker registered: {user.id}")
            return result
        except HTTPException:
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"Seeker registration failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Registration failed. Please try again.",
            )
