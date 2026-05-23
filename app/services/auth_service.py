from fastapi import HTTPException, status
from loguru import logger
from app.repositories.user_repository import UserRepository
from app.schemas.auth_schema import AuthResponseSchema, SeekerRegisterSchema
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import Security
from app.models.user_model import Role
from datetime import timedelta
from app.core.config import settings


class AuthService:

    @staticmethod
    async def register_seeker(
        data: SeekerRegisterSchema,
        db: AsyncSession,
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
            user = await user_repo.create(
                phone_en=data.phone,
                password_hash=Security.hash_password(data.password),
                role=Role.SEEKER,
            )
            await db.commit()
            await db.refresh(user)

            logger.success(f"Seeker registered: {user.id}")

            access_token = Security.create_access_token(
                subject=str(user.id),
                expires_delta=timedelta(
                    minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
            )
            # TODO: return and refresh tokens, see security_file_fix.md

            return AuthResponseSchema(
                access_token=access_token,
                token_type="bearer",
                role=user.role.value,
                user_id=user.id,
            )
        except Exception as e:
            await db.rollback()
            logger.error(f"Seeker registration failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Registration failed. Please try again.",
            )
