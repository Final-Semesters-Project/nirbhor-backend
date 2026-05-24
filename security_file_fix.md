## Issues in `security.py`

**Issue 1 — Access and refresh tokens use the same secret and algorithm**

If someone gets your access token secret, they can forge refresh tokens too. Add a `token_type` claim to distinguish them:

```python
# access token payload
payload = {
    "sub": str(subject),
    "type": "access",      # ← add this
    "iat": int(datetime.now(timezone.utc).timestamp()),
    "exp": int(expire.timestamp()),
}

# refresh token payload
payload = {
    "sub": str(subject),
    "type": "refresh",     # ← add this
    "iat": int(datetime.now(timezone.utc).timestamp()),
    "exp": int(expire.timestamp()),
}
```

Then verify token type when decoding:

```python
@staticmethod
def decode_access_token(token: str | None) -> Dict[str, Any] | None:
    if token is None:
        return None
    try:
        payload = jwt.decode(...)
        if payload.get("type") != "access":    # ← verify type
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )
        return payload
    except ExpiredSignatureError:
        ...
```

**Issue 2 — Typo in WWW-Authenticate header**

```python
# ❌ wrong — lowercase and wrong spelling
headers={"www-Authentication": "Bearer"}

# ✅ correct — standard header name
headers={"WWW-Authenticate": "Bearer"}
```

This is in your `JWTError` handler in `decode_refresh_token`. Fix it.

**Issue 3 — `role` missing from token payload**

Your `get_current_user` will need to know the user's role for authorization. Add it to the token so you don't need a DB query just to check role:

```python
payload = {
    "sub": str(subject),
    "role": role,          # ← add role
    "type": "access",
    "iat": int(datetime.now(timezone.utc).timestamp()),
    "exp": int(expire.timestamp()),
}
```

Update `create_access_token` signature:

```python
@staticmethod
def create_access_token(subject: str, role: str, expires_delta: Optional[timedelta] = None) -> str:
```

---

## How to Send and Store Tokens

**On registration/login — return access token in response body, refresh token in HttpOnly cookie:**

```python
# auth_service.py
from fastapi.responses import JSONResponse
from fastapi import Response

@staticmethod
async def register_seeker(data: SeekerRegisterSchema, db: AsyncSession, response: Response) -> dict:
    # ... create user ...

    access_token = Security.create_access_token(
        subject=str(user.id),
        role=user.role.value,
    )
    refresh_token = Security.create_refresh_token(subject=str(user.id))

    # store refresh token in DB
    session_repo = UserSessionRepository(db)
    await session_repo.create(
        user_id=user.id,
        refresh_token=refresh_token,
        device_info=None,  # pass from request headers later
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
    )

    await db.commit()

    # set refresh token as HttpOnly cookie — JS cannot read this, XSS safe
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,      # JS cannot access
        secure=True,        # HTTPS only (set False in dev)
        samesite="lax",     # CSRF protection
        max_age=settings.REFRESH_TOKEN_EXPIRE_MINUTES * 60,
    )

    # access token in response body — frontend stores in memory (NOT localStorage)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role.value,
        "user_id": str(user.id),
    }
```

Update the router to pass `response`:

```python
# auth_router.py
@router.post("/register/seeker", response_model=AuthResponseSchema, status_code=201)
async def register_seeker(
    data: SeekerRegisterSchema,
    response: Response,                        # ← inject Response
    db: AsyncSession = Depends(get_db_session),
):
    return await AuthService.register_seeker(data, db, response)
```

**Why this pattern:**

| Storage | Access Token | Refresh Token |
|---------|-------------|---------------|
| localStorage | ❌ XSS vulnerable | ❌ never |
| Memory (JS var) | ✅ best | ❌ lost on refresh |
| HttpOnly Cookie | ✅ ok | ✅ best |

Access token lives in JS memory (lost on page refresh — frontend calls `/auth/refresh` on startup). Refresh token in HttpOnly cookie survives page refreshes and can't be stolen by XSS.

---

## Complete `get_current_user` Dependency

```python
# app/core/dependencies.py
import uuid
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger
from app.core.security import Security
from app.db.session import get_db_session
from app.models.user_model import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db_session),
) -> User:
    # decode_access_token raises HTTPException itself if invalid/expired
    payload = Security.decode_access_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # fetch user from DB
    user = await db.get(User, uuid.UUID(user_id))

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is suspended",
        )

    return user


# Role-based dependencies — build on top of get_current_user
async def get_current_seeker(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role != UserRole.SEEKER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seekers only",
        )
    return current_user


async def get_current_provider(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role != UserRole.PROVIDER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Providers only",
        )
    return current_user


async def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admins only",
        )
    return current_user
```

Usage in routes:

```python
# any authenticated user
@router.get("/profile")
async def get_profile(current_user: User = Depends(get_current_user)):
    ...

# seekers only
@router.post("/bookings")
async def create_booking(current_user: User = Depends(get_current_seeker)):
    ...

# providers only
@router.post("/urgent/accept")
async def accept_urgent(current_user: User = Depends(get_current_provider)):
    ...

# admins only
@router.get("/admin/users")
async def list_users(current_user: User = Depends(get_current_admin)):
    ...
```

---

## One Thing You're Missing — `UserSessionRepository`

You need this before registration works end-to-end:

```python
# app/repositories/user_session_repository.py
import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.models.user_session_model import UserSession
from app.repositories.base import BaseRepository


class UserSessionRepository(BaseRepository[UserSession]):
    def __init__(self, db: AsyncSession):
        super().__init__(UserSession, db)

    async def get_by_refresh_token(self, token: str) -> UserSession | None:
        return await self.db.scalar(
            select(UserSession).where(UserSession.refresh_token == token)
        )

    async def delete_by_refresh_token(self, token: str) -> None:
        await self.db.execute(
            delete(UserSession).where(UserSession.refresh_token == token)
        )

    async def delete_all_for_user(self, user_id: uuid.UUID) -> None:
        """Used for logout-all-devices"""
        await self.db.execute(
            delete(UserSession).where(UserSession.user_id == user_id)
        )
```