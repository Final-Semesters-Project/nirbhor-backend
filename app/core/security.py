from passlib.context import CryptContext
from fastapi import HTTPException, status
from jose import jwt, JWTError, ExpiredSignatureError
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from loguru import logger
from app.core.config import settings


password_context = CryptContext(
    schemes=["argon2", "bcrypt"], deprecated="auto")


class Security:

    # hash password
    @staticmethod
    def hash_password(password: str) -> str:
        return password_context.hash(password)

    # verify password
    @staticmethod
    def verify_password(
        plain_password: str,  # from request
        hashed_password: str  # from db
    ) -> bool:

        return password_context.verify(plain_password, hashed_password)

    # create access token
    @staticmethod
    def create_access_token(
        subject: str,  # uuid
        expires_delta: Optional[timedelta] = None
    ) -> str:

        # create JWT access token
        expire = datetime.now(timezone.utc) + (expires_delta or timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))  # set the expiration time

        payload = {
            "sub": str(subject),
            # issued at time
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "exp": int(expire.timestamp()),  # expiration time
        }

        # this is the access token
        token = jwt.encode(payload, settings.SECRET_KEY.get_secret_value(),
                           algorithm=settings.ALGORITHM)

        return token

    # create refresh token
    @staticmethod
    def create_refresh_token(
        subject: str,  # uuid
        expires_delta: Optional[timedelta] = None
    ) -> str:
        # create jwt refresh token to re-generate the access token
        expire = datetime.now(timezone.utc) + (expires_delta or timedelta(
            minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES))

        payload = {
            "sub": str(subject),
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "exp": int(expire.timestamp()),
        }

        # refresh token
        refresh_token = jwt.encode(payload, settings.SECRET_KEY.get_secret_value(),
                                   algorithm=settings.ALGORITHM)

        return refresh_token

    # decode access token
    @staticmethod
    def decode_access_token(token: str | None) -> Dict[str, Any] | None:
        if token is None:
            return None

        try:
            # returns the payload (sub, iat, exp)
            return jwt.decode(token, settings.SECRET_KEY.get_secret_value(), algorithms=[settings.ALGORITHM])
        except ExpiredSignatureError:
            logger.error("Expired token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except JWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e),
                headers={"www-Authentication": "Bearer"},
            )

    # decode refresh token
    @staticmethod
    def decode_refresh_token(token: str | None) -> Dict[str, Any] | None:
        if token is None:
            return None

        try:
            # returns the payload (sub, iat, exp)
            return jwt.decode(token, settings.SECRET_KEY.get_secret_value(), algorithms=[settings.ALGORITHM])
        except ExpiredSignatureError:
            logger.error("Expired refresh token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh Token expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except JWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e),
                headers={"www-Authentication": "Bearer"},
            )
