import secrets

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
        role: str,
        expires_delta: Optional[timedelta] = None
    ) -> str:

        # create JWT access token
        expire = datetime.now(timezone.utc) + (expires_delta or timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))  # set the expiration time

        payload = {
            "sub": str(subject),
            "type": "access",
            "role": role,
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
            "type": "refresh",
            # jti(JWT ID) is unique ID per token - fixes duplicate constraint. Prevents error when same user re-generates token at the same millisecond
            "jti": secrets.token_hex(16),
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
            # returns the payload (sub, type, iat, exp)
            payload = jwt.decode(
                token, settings.SECRET_KEY.get_secret_value(), algorithms=[settings.ALGORITHM])

            # reject refresh tokens used as access tokens
            if payload.get("type") != "access":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token type",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            return payload
        except ExpiredSignatureError:
            logger.error("Access Token Expired")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except JWTError as e:
            logger.error(f"Invalid Token: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # decode refresh token
    @staticmethod
    def decode_refresh_token(token: str | None) -> Dict[str, Any] | None:
        if token is None:
            return None

        try:
            payload = jwt.decode(
                token, settings.SECRET_KEY.get_secret_value(), algorithms=[settings.ALGORITHM])
            # returns the payload (sub, iat, exp)

            # reject access tokens used as refresh tokens
            if payload.get("type") != "refresh":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token type",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            return payload
        except ExpiredSignatureError:
            logger.error("Refresh token expired")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh Token expired. Please login again",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except JWTError as e:
            logger.error(f"Invalid Token: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )
