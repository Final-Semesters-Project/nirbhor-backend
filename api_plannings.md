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



why sqlalchemy returns direct objects or tuples when I write the query in service layer
but it returns memory locations <> when I write the query in repository layer?


what will I answer if teacher asks why didn't I use pubsub for notifications? Why used FCM instead?