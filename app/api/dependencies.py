from cachetools.func import ttl_cache
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
# from app.core.cache_user import CacheService
# from app.core.jwt import decode_access_token
from app.core.cache import TokenBlockListService, UserCacheService
from app.core.security import Security
from app.db.session import get_db_session
from app.models.user_model import User, Role
import uuid

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")


async def get_current_user(
        request: Request,
        token: str = Depends(oauth2_scheme),
        db: AsyncSession = Depends(get_db_session)
) -> User | None:

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        if TokenBlockListService.is_blocked(token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # get the payload from token
        payload = Security.decode_access_token(token)

        if payload is None:
            raise credentials_exception

        # get the uuid
        user_id = str(payload.get("sub"))

        if not user_id:
            raise credentials_exception

        # get the user from cache
        cached_user = UserCacheService.get(user_id)
        if cached_user is not None:
            if not cached_user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Account is suspended",
                )
            return cached_user

        # get the user from database if not in cache
        user = await db.get(User, user_id)

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is suspended"
            )

        # create cache
        UserCacheService.set(user_id, user)

        return user
    except HTTPException:
        raise
    except Exception:
        raise credentials_exception


# ────────────── Role guards ──────────────
async def get_current_seeker(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role != Role.SEEKER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is for seekers only",
        )
    return current_user


async def get_current_provider(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role != Role.PROVIDER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is for providers only",
        )
    return current_user


async def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role != Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is for admins only",
        )
    return current_user
