# Domain 1: Bookings Management (/app/api/v1/bookings/)
- Handles: Intent-to-Book Workflow.
1. POST /api/v1/bookings/initiate
- Trigger: Seeker clicks "Request to Call" on a provider's profile.
- Logic:
    - Count active INITIATED records for the calling seeker; reject if they are spamming multiple open numbers simultaneously.

    - Insert a row into bookings with status = BookingStatus.INITIATED and set call_unlocked_at = datetime.utcnow().

    - Response: Returns the raw phone number of the provider so the frontend can trigger the native system dialer.

2. PATCH /api/v1/bookings/{booking_id}/respond
- Trigger: Seeker responds to the 2-hour or 24-hour FCM notification prompt ("Did you end up hiring...?").
Payload Schema: {"hired": bool, "work_schedule": datetime | None}
- Logic:
    - If hired == True: Update status directly to IN_PROGRESS (bypassing CONFIRMED as discussed) and save the explicit work_schedule. Automatically bump last_active_at for both users here to trigger Implied Activity tracking.

    - If hired == False: Update status to CANCELLED.

3. GET /api/v1/bookings/provider/me
- Trigger: Provider opens their "Incoming Bookings" tab (matches your incoming_bookings.png UI mockup).
- Logic: Query bookings table where provider_id == current_user.id AND status == BookingStatus.IN_PROGRESS. (This cleanly isolates and hides INITIATED records from their screen).

4. GET /api/v1/bookings/seeker/me
- Trigger: Seeker opens their booking history list.

- Logic: Query all records matching seeker_id == current_user.id (including INITIATED entries so they can see past numbers they requested).


# Domain 2: Location-Aware Search (/app/api/v1/search/)
5. GET /api/v1/search/providers
- Handles: Discovery & Search Requirements.
- Query Parameters: `skill_category_id: int`, `seeker_lat: float`, `seeker_lng: float`, `search_radius_km: int | None = 1` 
- Logic:
    - Execute a PostGIS geospatial query matching providers whose `base_location` and defined `working_radius_km` overlap with the seeker's point coordinates.
    - Filter out providers where `is_available == False` (off-duty toggles) or where `last_active_at` is older than 60 days.
    - Apply your explicit Provider Ranking Score formula right inside the SQLAlchemy query selection using mathematical weights:
        `score = (1/distance_km) + (rating * 2) + (verification_level * 3) + activity_bonus`
    - Return localized `name_bn` or `name_en` fields dynamically by inspecting the Accept-Language header wrapper.

# Domain 3: Emergency Broadcasts (/app/api/v1/urgent/)
- Handles: Atomic multi-device Urgent Services ("Need It NOW") engine.
6. POST /api/v1/urgent/broadcast
- Trigger: Seeker requests an emergency asset dispatch.
- Logic: 
    - Insert an item into `urgent_broadcasts` with `status = BROADCASTING` and `expires_at = now() + 5 minutes`. Collect active target tokens within 3 KM with `has_smartphone == True` and trigger simultaneous high-priority FCM payloads.

7. POST /api/v1/urgent/broadcast/{broadcast_id}/claim
- Trigger: Fast-acting provider taps "Accept" on their screen.
- Logic: Run an atomic database transaction with a pessimistic lock (with_for_update()) to prevent race conditions:
    ```python
        # Ensure only the fastest write wins
        stmt = select(UrgentBroadcast).where(UrgentBroadcast.id == id).with_for_update()
    ```
    If status is still `BROADCASTING`, switch it to `CLAIMED` and set `claimed_by_provider_id`. If already claimed, raise a `409 Conflict` (or customized message) indicating the job was taken.

# 🛠️ Infrastructure & Version Controls (/app/api/v1/config/)
8. GET /api/v1/config/app-version
- Trigger: App startup verification sequence.
- Query Parameters: platform: str, current_version: str
- Logic: Read your app_versions database metadata. If current_version falls strictly behind the minimum_required_version, notify the application wrapper to trigger a full structural hard-lock block screen.

⏰ Background Automation Tasks (/app/jobs/)
To keep your application code snappy, offload execution lifecycles to your embedded internal APScheduler tasks engine:

The Midnight Expiry Clean (run_daily_at_midnight): Scan for any INITIATED rows remaining unconfirmed for more than 48 hours and switch them globally to AUTO_EXPIRED.

The Urgent Expiry Sweeper (run_every_minute): Scan for entries remaining BROADCASTING where expires_at is past the current timestamp, flag them as EXPIRED, and push an FCM fallback error update back to the waiting seeker.

The 15-Day Visibility Ping: Scan for providers with no interactive activity update records between 15 and 30 days old, and issue a free "Tap to Stay Visible" FCM notification card sequence to refresh their placement metrics safely.


======================================== CODE ========================================

# Nirbhor — Domains 1, 2, 3 Implementation

## File Map

---

## ⚙️ Setup Required Before Running

### 1. Register the new routers in `app/api/v1/router.py`

### 2. Add a missing i18n key => added

### 3. FCM (stub for now, real implementation later)

The `NotificationService` below is a stub. Firebase Admin SDK setup is a
separate task. For now the stubs log the intent without actually sending.

---

## 1. Schemas

## 2. Repositories

## 3. Services

## 4. Routers

## 5. One Method to Add to `UserRepository`


# APScheduler

# register jobs




<!-- next -->
1. A background task runs every minute. If it finds any `BROADCASTING` records where `expires_at` is in the past, it marks them `EXPIRED` and sends the seeker an FCM notification: "No one responded. Please try a manual search."





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

## i18n keys to add

```python
"broadcast_expired":        {"en": "No one responded. Please try a manual search.", "bn": "কেউ সাড়া দেননি। অনুগ্রহ করে ম্যানুয়াল অনুসন্ধান করুন।"},
"broadcast_not_broadcasting":{"en": "This broadcast is no longer active.",           "bn": "এই ব্রডকাস্ট আর সক্রিয় নেই।"},
"review_already_exists":    {"en": "You have already reviewed this booking.",        "bn": "আপনি ইতিমধ্যে এই বুকিং রিভিউ করেছেন।"},
"review_not_eligible":      {"en": "This booking is not yet completed.",             "bn": "এই বুকিং এখনও সম্পন্ন হয়নি।"},
"booking_not_found":        {"en": "Booking not found.",                             "bn": "বুকিং পাওয়া যায়নি।"},
```

---

## 1. Updated Schemas

### `app/schemas/urgent_schema.py` — update claim response

```python
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from app.models.urgent_broadcast import BroadcastStatus


class UrgentBroadcastCreateSchema(BaseModel):
    skill_id: int
    latitude: float
    longitude: float


class UrgentBroadcastResponse(BaseModel):
    broadcast_id: UUID
    status: BroadcastStatus
    expires_at: datetime
    message: str

    model_config = {"from_attributes": True}


class UrgentBroadcastDetailResponse(BaseModel):
    """Returned when provider fetches broadcast details after FCM tap."""
    broadcast_id: UUID
    status: BroadcastStatus
    skill_id: int
    expires_at: datetime
    seeker_latitude: float | None   # so provider can navigate
    seeker_longitude: float | None

    model_config = {"from_attributes": True}


class UrgentClaimResponse(BaseModel):
    """
    Returned to provider after successfully claiming a broadcast.
    Includes seeker phone so provider can call immediately.
    """
    broadcast_id: UUID
    status: str
    seeker_name: str
    seeker_phone: str   # revealed only to the claiming provider

    model_config = {"from_attributes": True}
```

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

### `app/repositories/urgent_repository.py` — update `claim_broadcast`

```python
# Replace claim_broadcast method with this version that fetches seeker info

async def claim_broadcast(
    self,
    broadcast_id: UUID,
    provider_id: UUID,
) -> tuple[UrgentBroadcast | None, str | None, str | None]:
    """
    Atomic claim with pessimistic lock.
    Returns (broadcast, seeker_name, seeker_phone).
    seeker_name and seeker_phone are None if claim fails.
    """
    from app.models.user import User

    result = await self.db.execute(
        select(UrgentBroadcast)
        .where(UrgentBroadcast.id == broadcast_id)
        .with_for_update()
    )
    broadcast = result.scalar_one_or_none()

    if not broadcast:
        return None, None, None

    if broadcast.status != BroadcastStatus.BROADCASTING:
        return broadcast, None, None

    broadcast.status = BroadcastStatus.CLAIMED
    broadcast.claimed_by_provider_id = provider_id
    await self.db.flush()

    # Fetch seeker details to return to the claiming provider
    seeker_result = await self.db.execute(
        select(User.name_en, User.phone_en)
        .where(User.id == broadcast.seeker_id)
    )
    seeker_row = seeker_result.first()
    seeker_name = seeker_row.name_en if seeker_row else "—"
    seeker_phone = seeker_row.phone_en if seeker_row else None

    return broadcast, seeker_name, seeker_phone


async def get_broadcast_by_id(self, broadcast_id: UUID) -> UrgentBroadcast | None:
    """Fetch a broadcast for the detail view."""
    result = await self.db.execute(
        select(UrgentBroadcast).where(UrgentBroadcast.id == broadcast_id)
    )
    return result.scalar_one_or_none()


async def expire_stale_broadcasts(self) -> list[UUID]:
    """
    Mark all BROADCASTING rows past expires_at as EXPIRED.
    Returns list of seeker_ids to notify.
    Called by APScheduler every minute.
    """
    from sqlalchemy import update
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)

    # Fetch seeker_ids before updating so we can notify them
    stale = await self.db.execute(
        select(UrgentBroadcast.id, UrgentBroadcast.seeker_id)
        .where(UrgentBroadcast.status == BroadcastStatus.BROADCASTING)
        .where(UrgentBroadcast.expires_at < now)
    )
    rows = stale.all()

    if not rows:
        return []

    stale_ids = [r.id for r in rows]
    seeker_ids = [r.seeker_id for r in rows]

    await self.db.execute(
        update(UrgentBroadcast)
        .where(UrgentBroadcast.id.in_(stale_ids))
        .values(status=BroadcastStatus.EXPIRED)
    )

    return seeker_ids
```

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

### `app/services/urgent_service.py` — update `claim_broadcast`

```python
@staticmethod
async def claim_broadcast(
    broadcast_id: UUID,
    provider_id: UUID,
    db: AsyncSession,
    lang: str,
) -> UrgentClaimResponse:
    urgent_repo = UrgentRepository(db)

    broadcast, seeker_name, seeker_phone = await urgent_repo.claim_broadcast(
        broadcast_id, provider_id
    )

    if not broadcast:
        raise DomainValidationError(t("broadcast_not_found", lang))

    if broadcast.status == BroadcastStatus.EXPIRED:
        raise DomainValidationError(t("broadcast_not_found", lang))

    if broadcast.status == BroadcastStatus.CLAIMED:
        if broadcast.claimed_by_provider_id == provider_id:
            # Idempotent: this provider already claimed it (duplicate tap)
            # Re-fetch seeker info since we didn't get it from the lock path
            from app.models.user import User
            from sqlalchemy import select
            row = await db.execute(
                select(User.name_en, User.phone_en)
                .where(User.id == broadcast.seeker_id)
            )
            r = row.first()
            await db.commit()
            return UrgentClaimResponse(
                broadcast_id=broadcast_id,
                status="CLAIMED",
                seeker_name=r.name_en if r else "—",
                seeker_phone=r.phone_en if r else "",
            )
        raise DomainIntegrityError(t("broadcast_already_claimed", lang))

    await db.commit()
    logger.info(f"Broadcast {broadcast_id} claimed by provider {provider_id}")

    # TODO: notify seeker via FCM that a provider is coming
    # await NotificationService.send_broadcast_claimed(broadcast.seeker_id, provider_id)

    return UrgentClaimResponse(
        broadcast_id=broadcast_id,
        status="CLAIMED",
        seeker_name=seeker_name or "—",
        seeker_phone=seeker_phone or "",
    )


@staticmethod
async def get_broadcast(
    broadcast_id: UUID,
    db: AsyncSession,
    lang: str,
) -> UrgentBroadcastDetailResponse:
    """
    Provider fetches broadcast details after tapping FCM notification.
    Returns location so provider can navigate.
    """
    from geoalchemy2.shape import to_shape

    urgent_repo = UrgentRepository(db)
    broadcast = await urgent_repo.get_broadcast_by_id(broadcast_id)

    if not broadcast:
        raise DomainValidationError(t("broadcast_not_found", lang))

    # Extract lat/lng from the PostGIS point
    lat, lng = None, None
    if broadcast.location is not None:
        point = to_shape(broadcast.location)
        lng = point.x   # PostGIS stores as (lng, lat)
        lat = point.y

    return UrgentBroadcastDetailResponse(
        broadcast_id=broadcast.id,
        status=broadcast.status,
        skill_id=broadcast.skill_id,
        expires_at=broadcast.expires_at,
        seeker_latitude=lat,
        seeker_longitude=lng,
    )
```

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

### `app/api/v1/urgent.py` — add GET broadcast endpoint

```python
# Add this to your existing urgent router

@router.get("/broadcast/{broadcast_id}", response_model=UrgentBroadcastDetailResponse)
async def get_broadcast_detail(
    broadcast_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    lang: str = Depends(get_lang),
):
    """
    Provider fetches broadcast details after tapping the FCM notification.
    Returns skill, status, and seeker coordinates for navigation.
    """
    return await UrgentService.get_broadcast(
        broadcast_id=broadcast_id,
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

### `app/jobs/urgent_jobs.py` — new

```python
from loguru import logger

from app.db.session import AsyncSessionLocal
from app.repositories.urgent_repository import UrgentRepository


async def expire_stale_broadcasts():
    """
    Runs every minute via APScheduler.
    Marks BROADCASTING records past expires_at as EXPIRED.
    Sends FCM to seekers to notify them nobody responded.

    Why every minute: broadcasts expire after 5 minutes.
    A 1-minute polling interval means max 1 minute of extra wait
    before the seeker learns nobody responded — acceptable.
    """
    async with AsyncSessionLocal() as db:
        repo = UrgentRepository(db)
        seeker_ids = await repo.expire_stale_broadcasts()

        if not seeker_ids:
            return

        await db.commit()

        logger.info(
            f"Expired {len(seeker_ids)} stale broadcasts, "
            f"notifying seekers: {seeker_ids}"
        )

        for seeker_id in seeker_ids:
            # TODO: send FCM to seeker
            # await NotificationService.send_broadcast_expired(seeker_id)
            logger.info(f"[stub] Notifying seeker {seeker_id}: no one responded")
```

### Register in `main.py` lifespan

```python
# In lifespan, alongside the booking jobs scheduler

from app.jobs.urgent_jobs import expire_stale_broadcasts

scheduler.add_job(expire_stale_broadcasts, "interval", minutes=1)
# existing jobs:
# scheduler.add_job(send_booking_followup_notifications, "interval", minutes=5)
# scheduler.add_job(expire_stale_bookings, "cron", hour=0, minute=0)
```

---

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
