```
POST /api/v1/auth/register/seeker    ← name, phone, password
POST /api/v1/auth/register/provider  ← name, phone, password, skills, location, radius, has_smartphone
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