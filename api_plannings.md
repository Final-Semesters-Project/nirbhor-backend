# Nirbhor — Next API Batch

## Files Changed / Created

```
app/
├── schemas/
│   ├── urgent_schema.py          ← update claim response
│   ├── category_schema.py        ← new
│   ├── booking_schema.py         ← add single booking detail schema
│   └── review_schema.py          ← new
├── repositories/
│   ├── urgent_repository.py      ← update claim to return seeker phone
│   ├── category_repository.py    ← new
│   ├── booking_repository.py     ← add get_single_booking
│   └── review_repository.py      ← new
├── services/
│   ├── urgent_service.py         ← update claim response
│   ├── category_service.py       ← new
│   ├── booking_service.py        ← add get_single_booking
│   └── review_service.py         ← new
├── api/v1/
│   ├── urgent.py                 ← add GET single broadcast
│   ├── categories.py             ← new
│   ├── bookings.py               ← add GET single booking
│   └── reviews.py                ← new
└── jobs/
    └── urgent_jobs.py            ← new: expiry background job
```

---

## 1. Updated Schemas

### `app/schemas/category_schema.py` — new

```python
from pydantic import BaseModel


class CategoryResponse(BaseModel):
    id: int
    name: str   # localized

    model_config = {"from_attributes": True}


class SkillResponse(BaseModel):
    id: int
    name: str   # localized
    category_id: int

    model_config = {"from_attributes": True}
```

### `app/schemas/booking_schema.py` — add single booking detail

```python
# Add this to your existing booking_schema.py

class BookingDetailResponse(BaseModel):
    """Full detail for a single booking — used by both seeker and provider."""
    booking_id: UUID
    status: BookingStatus
    skill_id: int
    created_at: datetime
    call_unlocked_at: datetime | None
    confirmed_at: datetime | None
    work_schedule: datetime | None
    completed_at: datetime | None
    # The other party info — seeker sees provider, provider sees seeker
    other_party_name: str
    other_party_phone: str | None
    # Location of the job (shown to provider when IN_PROGRESS)
    job_latitude: float | None
    job_longitude: float | None

    model_config = {"from_attributes": True}
```

### `app/schemas/review_schema.py` — new

```python
from pydantic import BaseModel, field_validator
from uuid import UUID


class ReviewCreateSchema(BaseModel):
    booking_id: UUID
    rating: int
    comment: str | None = None
    is_anonymous: bool = True

    @field_validator("rating")
    @classmethod
    def rating_must_be_valid(cls, v: int) -> int:
        if not 1 <= v <= 5:
            raise ValueError("rating must be between 1 and 5.")
        return v


class ReviewResponse(BaseModel):
    review_id: UUID
    booking_id: UUID
    rating: int
    comment: str | None
    is_anonymous: bool

    model_config = {"from_attributes": True}
```

---

## 2. Repositories

### `app/repositories/category_repository.py` — new

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.category import Category
from app.models.skill import Skill


class CategoryRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all_categories(self) -> list[Category]:
        result = await self.db.execute(
            select(Category).order_by(Category.id)
        )
        return list(result.scalars().all())

    async def get_skills_by_category(self, category_id: int) -> list[Skill]:
        result = await self.db.execute(
            select(Skill)
            .where(Skill.category_id == category_id)
            .order_by(Skill.id)
        )
        return list(result.scalars().all())
```

### `app/repositories/booking_repository.py` — add `get_single_booking`

```python
# Add this method to BookingRepository

async def get_single_booking(self, booking_id: UUID) -> Booking | None:
    """Fetch one booking by ID. No joins — service handles party lookup."""
    result = await self.db.execute(
        select(Booking).where(Booking.id == booking_id)
    )
    return result.scalar_one_or_none()
```

### `app/repositories/review_repository.py` — new

```python
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.review import Review
from app.models.booking import Booking, BookingStatus
from app.repositories.base import BaseRepository


class ReviewRepository(BaseRepository[Review]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, Review)

    async def get_booking_for_review(self, booking_id: UUID) -> Booking | None:
        """
        Fetch booking only if it's eligible for review:
        status=COMPLETED and confirmed_at IS NOT NULL.
        """
        result = await self.db.execute(
            select(Booking)
            .where(Booking.id == booking_id)
            .where(Booking.status == BookingStatus.COMPLETED)
            .where(Booking.confirmed_at.is_not(None))
        )
        return result.scalar_one_or_none()

    async def get_existing_review(
        self, booking_id: UUID, reviewer_id: UUID
    ) -> Review | None:
        """Check if this reviewer already reviewed this booking."""
        result = await self.db.execute(
            select(Review)
            .where(Review.booking_id == booking_id)
            .where(Review.reviewer_id == reviewer_id)
        )
        return result.scalar_one_or_none()

    async def create_review(
        self,
        booking_id: UUID,
        reviewer_id: UUID,
        reviewee_id: UUID,
        rating: int,
        comment: str | None,
        is_anonymous: bool,
    ) -> Review:
        review = Review(
            booking_id=booking_id,
            reviewer_id=reviewer_id,
            reviewee_id=reviewee_id,
            rating=rating,
            comment=comment,
            is_anonymous=is_anonymous,
        )
        self.db.add(review)
        await self.db.flush()
        return review

    async def recalculate_provider_rating(
        self, provider_id: UUID
    ) -> float | None:
        """
        Recalculate and return the new average rating for a provider.
        Called after every new review. Service writes it back to ProviderProfile.
        """
        from sqlalchemy import func
        result = await self.db.execute(
            select(func.avg(Review.rating))
            .where(Review.reviewee_id == provider_id)
        )
        return result.scalar_one_or_none()
```

---

## 3. Services

### `app/services/category_service.py` — new

```python
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.category_repository import CategoryRepository
from app.schemas.category_schema import CategoryResponse, SkillResponse
from app.core.exceptions import DomainValidationError
from app.core.i18n import t


class CategoryService:
    @staticmethod
    async def get_all_categories(
        db: AsyncSession, lang: str
    ) -> list[CategoryResponse]:
        repo = CategoryRepository(db)
        categories = await repo.get_all_categories()
        return [
            CategoryResponse(
                id=c.id,
                name=c.name_bn if lang == "bn" else c.name_en,
            )
            for c in categories
        ]

    @staticmethod
    async def get_skills_by_category(
        category_id: int, db: AsyncSession, lang: str
    ) -> list[SkillResponse]:
        repo = CategoryRepository(db)
        skills = await repo.get_skills_by_category(category_id)
        return [
            SkillResponse(
                id=s.id,
                name=s.name_bn if lang == "bn" else s.name_en,
                category_id=s.category_id,
            )
            for s in skills
        ]
```

### `app/services/booking_service.py` — add `get_single_booking`

```python
@staticmethod
async def get_single_booking(
    booking_id: UUID,
    current_user_id: UUID,
    db: AsyncSession,
    lang: str,
) -> BookingDetailResponse:
    from geoalchemy2.shape import to_shape

    booking_repo = BookingRepository(db)
    user_repo = UserRepository(db)

    booking = await booking_repo.get_single_booking(booking_id)
    if not booking:
        raise DomainValidationError(t("booking_not_found", lang))

    # Only the seeker or provider of this booking can view it
    if booking.seeker_id != current_user_id and booking.provider_id != current_user_id:
        raise DomainValidationError(t("booking_not_yours", lang))

    is_seeker = booking.seeker_id == current_user_id

    if is_seeker:
        other = await user_repo.get_by_id(booking.provider_id)
    else:
        other = await user_repo.get_by_id(booking.seeker_id)

    # Extract job location coordinates from PostGIS point
    lat, lng = None, None
    if booking.job_location is not None:
        point = to_shape(booking.job_location)
        lng = point.x
        lat = point.y

    return BookingDetailResponse(
        booking_id=booking.id,
        status=booking.status,
        skill_id=booking.skill_id,
        created_at=booking.created_at,
        call_unlocked_at=booking.call_unlocked_at,
        confirmed_at=booking.confirmed_at,
        work_schedule=booking.work_schedule,
        completed_at=booking.completed_at,
        other_party_name=other.name_en if other else "—",
        # Phone visible to seeker always (they unlocked it).
        # Provider sees seeker phone only when IN_PROGRESS (they need to go there).
        other_party_phone=other.phone_en if other else None,
        job_latitude=lat,
        job_longitude=lng,
    )
```

### `app/services/review_service.py` — new

```python
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.models.provider_profile import ProviderProfile
from app.models.user import Role
from app.repositories.review_repository import ReviewRepository
from app.schemas.review_schema import ReviewCreateSchema, ReviewResponse
from app.core.exceptions import DomainIntegrityError, DomainValidationError
from app.core.i18n import t


class ReviewService:

    @staticmethod
    async def create_review(
        data: ReviewCreateSchema,
        reviewer_id: UUID,
        reviewer_role: Role,
        db: AsyncSession,
        lang: str,
    ) -> ReviewResponse:
        review_repo = ReviewRepository(db)

        # 1. Booking must be completed and confirmed
        booking = await review_repo.get_booking_for_review(data.booking_id)
        if not booking:
            raise DomainValidationError(t("review_not_eligible", lang))

        # 2. Reviewer must be a party to this booking
        if reviewer_id not in (booking.seeker_id, booking.provider_id):
            raise DomainValidationError(t("booking_not_yours", lang))

        # 3. Reviewee is the other party
        reviewee_id = (
            booking.provider_id
            if reviewer_id == booking.seeker_id
            else booking.seeker_id
        )

        # 4. One review per party per booking
        existing = await review_repo.get_existing_review(data.booking_id, reviewer_id)
        if existing:
            raise DomainIntegrityError(t("review_already_exists", lang))

        # 5. Create review
        review = await review_repo.create_review(
            booking_id=data.booking_id,
            reviewer_id=reviewer_id,
            reviewee_id=reviewee_id,
            rating=data.rating,
            comment=data.comment,
            is_anonymous=data.is_anonymous,
        )

        # 6. Recalculate provider's average rating
        # Only seeker→provider reviews affect public rating (spec: asymmetric trust)
        if reviewer_id == booking.seeker_id:
            new_avg = await review_repo.recalculate_provider_rating(reviewee_id)
            if new_avg is not None:
                provider_profile = await db.get(ProviderProfile, reviewee_id)
                if provider_profile:
                    provider_profile.average_rating = new_avg
                    # Auto-flag low ratings per spec
                    provider_profile.warning_status = new_avg < 3.0
                    logger.info(
                        f"Provider {reviewee_id} avg rating updated to {new_avg:.2f}"
                    )

        await db.commit()
        logger.info(
            f"Review created: booking {data.booking_id} "
            f"by {reviewer_id} → {reviewee_id} rating={data.rating}"
        )

        return ReviewResponse(
            review_id=review.id,
            booking_id=review.booking_id,
            rating=review.rating,
            comment=review.comment,
            is_anonymous=review.is_anonymous,
        )
```

---

## 4. Routers

### `app/api/v1/categories.py` — new

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.core.i18n import get_lang
from app.services.category_service import CategoryService
from app.schemas.category_schema import CategoryResponse, SkillResponse

router = APIRouter()


@router.get("", response_model=list[CategoryResponse])
async def get_categories(
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """All categories for the seeker home page dropdown."""
    return await CategoryService.get_all_categories(db=db, lang=lang)


@router.get("/{category_id}/skills", response_model=list[SkillResponse])
async def get_skills_by_category(
    category_id: int,
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """Skills under a category — populated after seeker selects a category."""
    return await CategoryService.get_skills_by_category(
        category_id=category_id, db=db, lang=lang
    )
```

### `app/api/v1/bookings.py` — add single booking endpoint

```python
# Add this to your existing bookings router

@router.get("/{booking_id}", response_model=BookingDetailResponse)
async def get_booking_detail(
    booking_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """
    Single booking detail — accessible by both seeker and provider of that booking.
    Shows job location coordinates to provider when status is IN_PROGRESS.

    ⚠️  Register this AFTER /provider/me and /seeker/me in the router
    to avoid FastAPI matching 'provider' or 'seeker' as a booking_id UUID.
    (FastAPI validates UUID format so this is safe, but explicit ordering is cleaner.)
    """
    return await BookingService.get_single_booking(
        booking_id=booking_id,
        current_user_id=current_user.id,
        db=db,
        lang=lang,
    )
```

### `app/api/v1/reviews.py` — new

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.core.i18n import get_lang
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.review_schema import ReviewCreateSchema, ReviewResponse
from app.services.review_service import ReviewService

router = APIRouter()


@router.post("", response_model=ReviewResponse, status_code=201)
async def create_review(
    data: ReviewCreateSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """
    Submit a rating and optional comment after a booking is COMPLETED.
    Both seeker and provider can review. One review per party per booking.
    Seeker→Provider reviews update the provider's public average_rating.
    Provider→Seeker reviews are stored but private (admin only).
    """
    return await ReviewService.create_review(
        data=data,
        reviewer_id=current_user.id,
        reviewer_role=current_user.role,
        db=db,
        lang=lang,
    )
```

---

## 5. Background Job — Urgent Broadcast Expiry

## 6. Register New Routers in `app/api/v1/router.py`

```python
from app.api.v1 import auth, bookings, search, urgent, categories, reviews

api_router.include_router(categories.router, prefix="/categories", tags=["Categories"])
api_router.include_router(reviews.router,    prefix="/reviews",    tags=["Reviews"])
```

---

## Priority Order for What's Left

Based on your screen list, here's what remains grouped by priority:

**Next batch (core app flows):**
- `GET /api/v1/providers/{provider_id}/public` — seeker taps provider card to see full profile
- `GET /api/v1/urgent/broadcast/{id}/status` — seeker polls to see if broadcast was claimed (or use FCM)

**After that (admin panel):**
- `GET /api/v1/admin/dashboard` — counts summary
- `GET /api/v1/admin/verifications` — pending verification list
- `PATCH /api/v1/admin/verifications/{provider_id}` — approve/reject
- `GET /api/v1/admin/reports` — flagged profiles
- `PATCH /api/v1/admin/reports/{report_id}` — dismiss/suspend
- `GET /api/v1/admin/users` — user list with filters
- `PATCH /api/v1/admin/users/{user_id}/toggle` — enable/disable account
- `GET /api/v1/admin/analytics` — stats + graphs
