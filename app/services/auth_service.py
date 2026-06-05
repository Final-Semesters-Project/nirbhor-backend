from asyncpg import ForeignKeyViolationError, UniqueViolationError
from fastapi import HTTPException, status, Response
from loguru import logger
from app.core.exceptions import DomainIntegrityError, DomainValidationError
from app.core.i18n import MESSAGES, t
from app.core.integrity_error_parser import parse_integrity_error
from app.repositories.provider_repository import ProviderRepository
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
from sqlalchemy.exc import IntegrityError


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
        lang: str,
        device_info: str | None = None,
    ) -> AuthResponseSchema:

        # re-validate with language context so error messages are translated
        data = SeekerRegisterSchema.model_validate(
            data.model_dump(),
            context={"lang": lang}
        )

        # Create an instance of UserRepository
        user_repo = UserRepository(db)

        # business rule: phone must be unique
        existing = await user_repo.get_by_phone(data.phone)
        if existing:
            raise DomainIntegrityError(
                error_message=t("phone_number_exists", lang),
            )

        try:
            # create user, create method comes from BaseRepository
            user = await user_repo.create(
                phone_en=data.phone,
                password_hash=Security.hash_password(data.password),
                role=Role.SEEKER,
                name_en=data.name_en,
                name_bn=data.name_bn,
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
        except IntegrityError as e:
            await db.rollback()
            raw = str(e.orig) if e.orig else str(e)
            readable = parse_integrity_error(raw, lang)

            # unwrap the original asyncpg exception to route correctly
            if isinstance(e.orig, ForeignKeyViolationError):
                logger.warning(f"FK violation in seeker registration: {raw}")
                raise DomainValidationError(
                    error_message=readable,
                    raw_error=raw
                )
            if isinstance(e.orig, UniqueViolationError):
                logger.warning(
                    f"Unique violation in seeker registration: {raw}")
                raise DomainIntegrityError(
                    error_message=readable,
                    raw_error=raw
                )
            logger.error(
                f"Unhandled IntegrityError in seeker registration: {raw}")
            raise DomainIntegrityError(error_message=readable, raw_error=raw)
        except (DomainIntegrityError, DomainValidationError):
            # let domain exceptions bubble up untouched to the global handler
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"Unexpected error in seeker registration: {e}")
            raise

    # register provider
    @staticmethod
    async def register_provider(
        data: ProviderRegisterSchema,
        db: AsyncSession,
        response: Response,
        lang: str,
        device_info: str | None = None,
    ) -> AuthResponseSchema:

        # re-validate with language context so error messages are translated
        data = ProviderRegisterSchema.model_validate(
            data.model_dump(),
            context={"lang": lang}
        )

        # Create an instance of UserRepository
        user_repo = UserRepository(db)
        provider_repo = ProviderRepository(db)

        # business rule: phone must be unique
        existing = await user_repo.get_by_phone(data.phone)
        if existing:
            raise DomainIntegrityError(
                error_message=t("phone_number_exists", lang),
            )

        try:
            # create user, create method comes from BaseRepository
            user = await user_repo.create(
                name_en=data.name_en,
                name_bn=data.name_bn,
                phone_en=data.phone,
                password_hash=Security.hash_password(data.password),
                role=Role.PROVIDER,
            )

            # create provider profile
            await provider_repo.create_profile(
                has_smartphone=data.has_smartphone,
                latitude=data.latitude,
                longitude=data.longitude,
                working_radius_km=data.working_radius_km,
                user_id=user.id
            )

            await provider_repo.add_skills(user.id, data.skill_ids)

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

            logger.success(f"Provider registered: {user.id}")
            return result
        except IntegrityError as e:
            await db.rollback()
            raw = str(e.orig) if e.orig else str(e)
            readable = parse_integrity_error(raw, lang)

            # e.orig may be a string (SQLAlchemy asyncpg dialect behavior) or
            # the actual asyncpg exception — handle both cases
            is_fk = (
                isinstance(e.orig, ForeignKeyViolationError)
                or "ForeignKeyViolationError" in raw
            )
            is_unique = (
                isinstance(e.orig, UniqueViolationError)
                or "UniqueViolationError" in raw
            )

            # unwrap the original asyncpg exception to route correctly
            if is_fk:
                logger.warning(f"FK violation in provider registration: {raw}")
                raise DomainValidationError(
                    error_message=readable,
                    raw_error=raw
                )
            if is_unique:
                logger.warning(
                    f"Unique violation in provider registration: {raw}")
                raise DomainIntegrityError(
                    error_message=readable,
                    raw_error=raw
                )

            logger.error(
                f"Unhandled IntegrityError in provider registration: {raw}")
            raise DomainIntegrityError(error_message=readable, raw_error=raw)
        except (DomainIntegrityError, DomainValidationError):
            # let domain exceptions bubble up untouched to the global handler
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"Unexpected error in provider registration: {e}")
            # don't convert to HTTPException — let global handler produce the 500
            raise

    @staticmethod
    async def password_login(
        response: Response,
        username: str,
        password: str,
        db: AsyncSession,
        lang: str,
        device_info: str | None = None,
    ) -> AuthResponseSchema:
        user_repo = UserRepository(db)

        # 1. Find user by phone
        user = await user_repo.get_by_phone(username)

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=t("invalid_credentials", lang),
            )

        # 2. Verify password
        if not Security.verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=t("invalid_credentials", lang),
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 3. Check is_active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=t("account_suspended", lang),
            )

        # 4. Create new access token, refresh token, Store refresh token, Set refresh token in HttpOnly cookie
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
        logger.success(
            f"User logged in: {user.id} | role: {user.role.value}")

        return result
