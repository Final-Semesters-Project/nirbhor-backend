# app/repositories/base.py
```python
from typing import Generic, TypeVar, Type
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.base import Base
import uuid

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Generic repository with common CRUD operations.
    Specific repositories inherit this and add complex queries.
    """

    def __init__(self, model: Type[ModelType], db: AsyncSession):
        self.model = model
        self.db = db

    async def get_by_id(self, id: uuid.UUID) -> ModelType | None:
        return await self.db.get(self.model, id)

    async def create(self, **kwargs) -> ModelType:
        instance = self.model(**kwargs)
        self.db.add(instance)
        await self.db.flush()  # gets PK without committing
        return instance

    async def update(self, instance: ModelType, **kwargs) -> ModelType:
        for key, value in kwargs.items():
            setattr(instance, key, value)
        await self.db.flush()
        return instance

    async def delete(self, instance: ModelType) -> None:
        await self.db.delete(instance)
        await self.db.flush()

    async def get_all(self) -> list[ModelType]:
        result = await self.db.execute(select(self.model))
        return result.scalars().all()
```

# app/repositories/user_repository.py
```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user_model import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, db: AsyncSession):
        super().__init__(User, db)

    async def get_by_phone(self, phone: str) -> User | None:
        return await self.db.scalar(
            select(User).where(User.phone_en == phone)
        )
```


```
POST /api/v1/auth/register/seeker    ← name, phone, password
POST /api/v1/auth/register/provider  ← name, phone, password, skills, location, radius, has_smartphone
```

```python
from pydantic import BaseModel, field_validator
import re


def validate_phone(phone: str) -> str:
    """Validates Bangladeshi phone numbers: 01XXXXXXXXX"""
    pattern = r'^01[3-9]\d{8}$'
    if not re.match(pattern, phone):
        raise ValueError("Invalid Bangladeshi phone number. Must be 11 digits starting with 01")
    return phone


class SeekerRegisterSchema(BaseModel):
    name: str
    phone: str
    password: str

    @field_validator("phone")
    @classmethod
    def validate_phone_number(cls, v: str) -> str:
        return validate_phone(v)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class ProviderRegisterSchema(BaseModel):
    name: str
    phone: str
    password: str
    skill_ids: list[int]          # list of skill IDs from the skills table
    latitude: float               # seeker sends coordinates
    longitude: float
    working_radius_km: int
    has_smartphone: bool

    @field_validator("phone")
    @classmethod
    def validate_phone_number(cls, v: str) -> str:
        return validate_phone(v)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    @field_validator("working_radius_km")
    @classmethod
    def validate_radius(cls, v: int) -> int:
        if v < 1 or v > 50:
            raise ValueError("Working radius must be between 1 and 50 km")
        return v


class AuthResponseSchema(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: str

```

# app/repositories/provider_repository.py
```python
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.provider_profile_model import ProviderProfile
from app.models.provider_skills_link_model import ProviderSkillsLink
from app.repositories.base import BaseRepository


class ProviderRepository(BaseRepository[ProviderProfile]):
    def __init__(self, db: AsyncSession):
        super().__init__(ProviderProfile, db)

    async def create_profile(
        self,
        user_id: uuid.UUID,
        name_en: str,
        latitude: float,
        longitude: float,
        working_radius_km: int,
        has_smartphone: bool,
    ) -> ProviderProfile:
        # WKT (Well-Known Text) format for PostGIS point
        # POINT(longitude latitude) — note: longitude first, this is the GIS standard
        location_wkt = f"POINT({longitude} {latitude})"

        profile = ProviderProfile(
            user_id=user_id,
            name_en=name_en,
            base_location=location_wkt,
            working_radius_km=working_radius_km,
            has_smartphone=has_smartphone,
        )
        self.db.add(profile)
        await self.db.flush()
        return profile

    async def add_skills(
        self, provider_id: uuid.UUID, skill_ids: list[int]
    ) -> None:
        for skill_id in skill_ids:
            link = ProviderSkillsLink(
                provider_id=provider_id,
                skill_id=skill_id,
            )
            self.db.add(link)
        await self.db.flush()
```


# app/services/auth_service.py

```python
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from loguru import logger
from app.repositories.user_repository import UserRepository
from app.repositories.provider_repository import ProviderRepository
from app.models.user_model import UserRole
from app.schemas.auth_schema import SeekerRegisterSchema, ProviderRegisterSchema
from app.core.security import hash_password, create_access_token


class AuthService:

    @staticmethod
    async def register_seeker(
        data: SeekerRegisterSchema,
        db: AsyncSession,
    ) -> dict:
        user_repo = UserRepository(db)

        # BUSINESS RULE: phone must be unique
        existing = await user_repo.get_by_phone(data.phone)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this phone number already exists",
            )

        try:
            user = await user_repo.create(
                phone_en=data.phone,
                password_hash=hash_password(data.password),
                role=UserRole.SEEKER,
            )
            await db.commit()
            await db.refresh(user)

            logger.success(f"Seeker registered: {user.id}")

            access_token = create_access_token(
                subject=str(user.id),
                role=user.role.value,
            )
            return {
                "access_token": access_token,
                "token_type": "bearer",
                "role": user.role.value,
                "user_id": str(user.id),
            }

        except Exception as e:
            await db.rollback()
            logger.error(f"Seeker registration failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Registration failed. Please try again.",
            )

    @staticmethod
    async def register_provider(
        data: ProviderRegisterSchema,
        db: AsyncSession,
    ) -> dict:
        user_repo = UserRepository(db)
        provider_repo = ProviderRepository(db)

        # BUSINESS RULE: phone must be unique
        existing = await user_repo.get_by_phone(data.phone)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this phone number already exists",
            )

        try:
            # Step 1: create user row
            user = await user_repo.create(
                phone_en=data.phone,
                password_hash=hash_password(data.password),
                role=UserRole.PROVIDER,
            )

            # Step 2: create provider profile
            profile = await provider_repo.create_profile(
                user_id=user.id,
                name_en=data.name,
                latitude=data.latitude,
                longitude=data.longitude,
                working_radius_km=data.working_radius_km,
                has_smartphone=data.has_smartphone,
            )

            # Step 3: link skills
            await provider_repo.add_skills(
                provider_id=user.id,
                skill_ids=data.skill_ids,
            )

            # Single commit — all three writes are atomic
            await db.commit()
            await db.refresh(user)

            logger.success(f"Provider registered: {user.id}")

            access_token = create_access_token(
                subject=str(user.id),
                role=user.role.value,
            )
            return {
                "access_token": access_token,
                "token_type": "bearer",
                "role": user.role.value,
                "user_id": str(user.id),
            }

        except Exception as e:
            await db.rollback()
            logger.error(f"Provider registration failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Registration failed. Please try again.",
            )
```

# app/api/v1/auth_router.py
```python

from fastapi import APIRouter, Depends
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
    status_code=201,
    summary="Register a new seeker account",
)
async def register_seeker(
    data: SeekerRegisterSchema,
    db: AsyncSession = Depends(get_db_session),
):
    return await AuthService.register_seeker(data, db)


@router.post(
    "/register/provider",
    response_model=AuthResponseSchema,
    status_code=201,
    summary="Register a new provider account",
)
async def register_provider(
    data: ProviderRegisterSchema,
    db: AsyncSession = Depends(get_db_session),
):
    return await AuthService.register_provider(data, db)
```


# app/main.py
```python
from app.api.v1.auth_router import router as auth_router
app.include_router(auth_router, prefix="/api/v1")
```


```
User  →  ProviderProfile   (one user has one profile)
                            uselist=False on BOTH sides for 1-to-1

User  →  Bookings          (one user has many bookings)  
                            uselist=True (default) on User side
                            uselist=False on Booking side (many bookings → one user)
```