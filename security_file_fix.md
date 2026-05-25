## Issues in `security.py`

## How to Send and Store Tokens

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