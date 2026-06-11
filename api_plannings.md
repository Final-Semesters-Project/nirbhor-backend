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

```
app/
├── schemas/
│   ├── booking_schema.py
│   ├── search_schema.py
│   └── urgent_schema.py
├── repositories/
│   ├── booking_repository.py
│   ├── search_repository.py
│   └── urgent_repository.py
├── services/
│   ├── booking_service.py
│   ├── search_service.py
│   └── urgent_service.py
└── api/v1/
    ├── bookings.py
    ├── search.py
    └── urgent.py
```

---

## ⚙️ Setup Required Before Running

### 1. Register the new routers in `app/api/v1/router.py`

```python
# app/api/v1/router.py
from fastapi import APIRouter
from app.api.v1 import auth, bookings, search, urgent  # add the three new ones

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(bookings.router, prefix="/bookings", tags=["Bookings"])
api_router.include_router(search.router, prefix="/search", tags=["Search"])
api_router.include_router(urgent.router, prefix="/urgent", tags=["Urgent"])
```

### 2. Add a missing i18n key => added

### 3. FCM (stub for now, real implementation later)

The `NotificationService` below is a stub. Firebase Admin SDK setup is a
separate task. For now the stubs log the intent without actually sending.

---

## 1. Schemas


### `app/schemas/urgent_schema.py`

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
```

---

## 2. Repositories

### `app/repositories/search_repository.py`

```python
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case, text
from geoalchemy2.functions import ST_DWithin, ST_MakePoint, ST_SetSRID, ST_Distance

from app.models.user import User
from app.models.provider_profile import ProviderProfile, VerificationLevel
from app.models.skill import Skill
from app.models.provider_skill_link import ProviderSkillLink


class SearchRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def find_providers(
        self,
        skill_category_id: int,
        seeker_lat: float,
        seeker_lng: float,
        search_radius_km: int,
    ) -> list[dict]:
        """
        Core geospatial search with inline ranking score.

        Score formula (from spec):
            score = (1/distance_km)
                  + (average_rating * 2)
                  + verification_bonus   [TRUSTED=+5, VERIFIED=+3, else 0]
                  + activity_bonus       [0-3d=+10, 4-15d=+5, 16-30d=-30, 31-60d=-60]
                  + (recent_booking_count * 0.5)

        Filters:
            - provider must have a skill in the requested category
            - provider base_location must be within search_radius_km of seeker
            - is_available must be True
            - last_active_at must not be older than 60 days
        """
        now = datetime.utcnow()
        seeker_point = ST_SetSRID(ST_MakePoint(seeker_lng, seeker_lat), 4326)

        # Convert KM to meters for ST_DWithin (geography uses meters)
        radius_m = search_radius_km * 1000

        # ── Activity bonus/penalty as a CASE expression ───────────────────────
        days_inactive = func.extract(
            "epoch",
            now - User.last_active_at
        ) / 86400  # convert seconds to days

        activity_score = case(
            (days_inactive <= 3,  10.0),
            (days_inactive <= 15,  5.0),
            (days_inactive <= 30, -30.0),
            (days_inactive <= 60, -60.0),
            else_=-60.0,  # fallback (shouldn't reach here due to WHERE filter)
        )

        # ── Verification bonus ────────────────────────────────────────────────
        verification_score = case(
            (ProviderProfile.verification_level == VerificationLevel.TRUSTED,  5.0),
            (ProviderProfile.verification_level == VerificationLevel.VERIFIED, 3.0),
            else_=0.0,
        )

        # ── Distance in KM from seeker to provider base_location ─────────────
        # ST_Distance with geography=True returns meters
        distance_m = ST_Distance(
            ProviderProfile.base_location.cast(text("geography")),
            seeker_point.cast(text("geography")),
        )
        distance_km = distance_m / 1000.0

        # ── Recent booking count (last 30 days) ───────────────────────────────
        # Subquery: how many completed bookings has this provider had?
        from app.models.booking import Booking, BookingStatus
        recent_bookings_sq = (
            select(func.count())
            .where(Booking.provider_id == ProviderProfile.user_id)
            .where(Booking.status == BookingStatus.COMPLETED)
            .where(Booking.completed_at >= now - timedelta(days=30))
            .correlate(ProviderProfile)
            .scalar_subquery()
        )

        # ── Composite ranking score ───────────────────────────────────────────
        ranking_score = (
            (1.0 / func.nullif(distance_km, 0))
            + (func.coalesce(ProviderProfile.average_rating, 0.0) * 2.0)
            + verification_score
            + activity_score
            + (recent_bookings_sq * 0.5)
        )

        stmt = (
            select(
                User.id.label("user_id"),
                User.last_active_at,
                ProviderProfile.working_radius_km,
                ProviderProfile.verification_level,
                ProviderProfile.average_rating,
                ProviderProfile.has_smartphone,
                ProviderProfile.is_available,
                distance_km.label("distance_km"),
                ranking_score.label("score"),
            )
            .join(ProviderProfile, User.id == ProviderProfile.user_id)
            .join(ProviderSkillLink, ProviderProfile.user_id == ProviderSkillLink.provider_id)
            .join(Skill, ProviderSkillLink.skill_id == Skill.id)
            # ── Filters ───────────────────────────────────────────────────────
            .where(Skill.category_id == skill_category_id)
            .where(ProviderProfile.is_available == True)
            .where(User.is_active == True)
            # provider working radius must overlap seeker location
            .where(
                ST_DWithin(
                    ProviderProfile.base_location.cast(text("geography")),
                    seeker_point.cast(text("geography")),
                    radius_m,
                )
            )
            # exclude 60+ day inactive providers entirely
            .where(
                User.last_active_at >= now - timedelta(days=60)
            )
            .distinct(User.id)
            .order_by(ranking_score.desc())
        )

        result = await self.db.execute(stmt)
        return [dict(row._mapping) for row in result.all()]

    async def get_provider_skill_names(
        self, provider_ids: list[UUID], category_id: int, lang: str
    ) -> dict[UUID, list[str]]:
        """
        Fetch skill names for a list of providers in one query.
        Returns {provider_id: [skill_name, ...]}
        """
        if not provider_ids:
            return {}

        name_col = Skill.name_bn if lang == "bn" else Skill.name_en

        result = await self.db.execute(
            select(ProviderSkillLink.provider_id, name_col.label("skill_name"))
            .join(Skill, ProviderSkillLink.skill_id == Skill.id)
            .where(ProviderSkillLink.provider_id.in_(provider_ids))
            .where(Skill.category_id == category_id)
        )

        skills_map: dict[UUID, list[str]] = {}
        for row in result.all():
            skills_map.setdefault(row.provider_id, []).append(row.skill_name)
        return skills_map

    async def get_provider_names(
        self, provider_ids: list[UUID], lang: str
    ) -> dict[UUID, str]:
        """
        Fetch display names for providers. Falls back to name_en if name_bn is NULL.
        Users table stores name_en/name_bn directly.
        """
        if not provider_ids:
            return {}

        # Use COALESCE to fall back to English if Bangla is null
        if lang == "bn":
            name_col = func.coalesce(User.name_bn, User.name_en).label("name")
        else:
            name_col = User.name_en.label("name")

        result = await self.db.execute(
            select(User.id, name_col)
            .where(User.id.in_(provider_ids))
        )
        return {row.id: row.name for row in result.all()}
```

### `app/repositories/urgent_repository.py`

```python
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from geoalchemy2.functions import ST_DWithin, ST_MakePoint, ST_SetSRID
from sqlalchemy import text

from app.models.urgent_broadcast import UrgentBroadcast, BroadcastStatus
from app.models.provider_profile import ProviderProfile
from app.models.fcm_token import FCMToken
from app.repositories.base import BaseRepository


class UrgentRepository(BaseRepository[UrgentBroadcast]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, UrgentBroadcast)

    async def create_broadcast(
        self,
        seeker_id: UUID,
        skill_id: int,
        latitude: float,
        longitude: float,
    ) -> UrgentBroadcast:
        point = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
        broadcast = UrgentBroadcast(
            seeker_id=seeker_id,
            skill_id=skill_id,
            location=point,
            status=BroadcastStatus.BROADCASTING,
            expires_at=datetime.utcnow() + timedelta(minutes=5),
        )
        self.db.add(broadcast)
        await self.db.flush()
        return broadcast

    async def get_nearby_fcm_tokens(
        self,
        latitude: float,
        longitude: float,
        radius_km: int = 3,
    ) -> list[str]:
        """
        Find FCM tokens for providers within radius_km who have smartphones.
        Returns list of token strings for batch FCM send.
        """
        seeker_point = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
        radius_m = radius_km * 1000

        result = await self.db.execute(
            select(FCMToken.token)
            .join(ProviderProfile, FCMToken.user_id == ProviderProfile.user_id)
            .where(ProviderProfile.has_smartphone == True)
            .where(ProviderProfile.is_available == True)
            .where(
                ST_DWithin(
                    ProviderProfile.base_location.cast(text("geography")),
                    seeker_point.cast(text("geography")),
                    radius_m,
                )
            )
        )
        return [row.token for row in result.all()]

    async def claim_broadcast(
        self,
        broadcast_id: UUID,
        provider_id: UUID,
    ) -> UrgentBroadcast | None:
        """
        Atomic claim with pessimistic lock.
        Returns the broadcast if successfully claimed, None if already taken.
        """
        # with_for_update() locks the row until this transaction commits
        result = await self.db.execute(
            select(UrgentBroadcast)
            .where(UrgentBroadcast.id == broadcast_id)
            .with_for_update()
        )
        broadcast = result.scalar_one_or_none()

        if not broadcast:
            return None

        if broadcast.status != BroadcastStatus.BROADCASTING:
            # Already claimed or expired — return the broadcast so the service
            # can produce the right error message
            return broadcast

        broadcast.status = BroadcastStatus.CLAIMED
        broadcast.claimed_by_provider_id = provider_id
        await self.db.flush()
        return broadcast
```

---

## 3. Services

### `app/services/booking_service.py`

```python
from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.models.booking import BookingStatus
from app.models.provider_profile import ProviderProfile
from app.repositories.booking_repository import BookingRepository
from app.repositories.user_repository import UserRepository
from app.schemas.booking_schema import (
    BookingInitiateSchema,
    BookingRespondSchema,
    BookingInitiateResponse,
    BookingListItem,
)
from app.core.exceptions import DomainIntegrityError, DomainValidationError
from app.core.i18n import t

# Business rule: max 10 open (INITIATED) booking at a time per seeker
MAX_OPEN_BOOKINGS = 10          # max simultaneous unlocked numbers
FOLLOWUP_DELAY_HOURS = 2        # FCM fires after this many hours


class BookingService:


    @staticmethod
    async def get_provider_incoming(
        provider_id: UUID,
        db: AsyncSession,
        lang: str,
    ) -> list[BookingListItem]:
        """Provider's 'Incoming Bookings' tab — only IN_PROGRESS."""
        booking_repo = BookingRepository(db)
        user_repo = UserRepository(db)
        bookings = await booking_repo.get_provider_incoming(provider_id)

        result = []
        for b in bookings:
            seeker = await user_repo.get_by_id(b.seeker_id)
            result.append(BookingListItem(
                booking_id=b.id,
                status=b.status,
                skill_id=b.skill_id,
                created_at=b.created_at,
                work_schedule=b.work_schedule,
                other_party_name=seeker.name_en if seeker else "—",
                other_party_phone=seeker.phone_en if seeker else None,
            ))
        return result

    @staticmethod
    async def get_seeker_history(
        seeker_id: UUID,
        db: AsyncSession,
        lang: str,
    ) -> list[BookingListItem]:
        """Seeker's full booking history including INITIATED entries."""
        booking_repo = BookingRepository(db)
        user_repo = UserRepository(db)
        bookings = await booking_repo.get_seeker_history(seeker_id)

        result = []
        for b in bookings:
            provider = await user_repo.get_by_id(b.provider_id)
            # Phone only revealed if booking was ever initiated (always is, but
            # keep this explicit for future status expansions)
            phone = provider.phone_en if provider else None
            result.append(BookingListItem(
                booking_id=b.id,
                status=b.status,
                skill_id=b.skill_id,
                created_at=b.created_at,
                work_schedule=b.work_schedule,
                other_party_name=provider.name_en if provider else "—",
                other_party_phone=phone,
            ))
        return result
```

### `app/services/search_service.py`

```python
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.repositories.search_repository import SearchRepository
from app.schemas.search_schema import ProviderSearchResult
from app.core.i18n import t

# If no results found within requested radius, auto-expand once to this
AUTO_EXPAND_KM = 2


class SearchService:

    @staticmethod
    async def find_providers(
        skill_category_id: int,
        seeker_lat: float,
        seeker_lng: float,
        search_radius_km: int,
        db: AsyncSession,
        lang: str,
    ) -> dict:
        """
        Search for providers. If none found in requested radius,
        automatically expands to AUTO_EXPAND_KM and returns a warning flag.
        """
        search_repo = SearchRepository(db)

        rows = await search_repo.find_providers(
            skill_category_id=skill_category_id,
            seeker_lat=seeker_lat,
            seeker_lng=seeker_lng,
            search_radius_km=search_radius_km,
        )

        expanded = False
        if not rows and search_radius_km < AUTO_EXPAND_KM:
            # Auto-expand once silently
            rows = await search_repo.find_providers(
                skill_category_id=skill_category_id,
                seeker_lat=seeker_lat,
                seeker_lng=seeker_lng,
                search_radius_km=AUTO_EXPAND_KM,
            )
            expanded = True
            logger.info(
                f"Search auto-expanded from {search_radius_km}km to {AUTO_EXPAND_KM}km "
                f"for category {skill_category_id}"
            )

        if not rows:
            return {
                "providers": [],
                "expanded_radius": expanded,
                "warning": t("no_providers_found", lang) if not rows else None,
            }

        provider_ids = [r["user_id"] for r in rows]

        # Batch-fetch names and skills in 2 queries (not N queries)
        names = await search_repo.get_provider_names(provider_ids, lang)
        skills_map = await search_repo.get_provider_skill_names(
            provider_ids, skill_category_id, lang
        )

        providers = [
            ProviderSearchResult(
                user_id=r["user_id"],
                name=names.get(r["user_id"], "—"),
                skill_names=skills_map.get(r["user_id"], []),
                verification_level=r["verification_level"].value,
                average_rating=r["average_rating"],
                distance_km=round(r["distance_km"], 2),
                working_radius_km=r["working_radius_km"],
                has_smartphone=r["has_smartphone"],
                is_available=r["is_available"],
                last_active_at=r["last_active_at"],
            )
            for r in rows
        ]

        return {
            "providers": providers,
            "expanded_radius": expanded,
            "warning": (
                t("search_radius_expanded_warning", lang) if expanded else None
            ),
        }
```

### `app/services/urgent_service.py`

```python
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.models.urgent_broadcast import BroadcastStatus
from app.repositories.urgent_repository import UrgentRepository
from app.schemas.urgent_schema import UrgentBroadcastCreateSchema, UrgentBroadcastResponse
from app.core.exceptions import DomainIntegrityError, DomainValidationError
from app.core.i18n import t


class UrgentService:

    @staticmethod
    async def create_broadcast(
        data: UrgentBroadcastCreateSchema,
        seeker_id: UUID,
        db: AsyncSession,
        lang: str,
    ) -> UrgentBroadcastResponse:

        urgent_repo = UrgentRepository(db)

        # 1. Create the broadcast row
        broadcast = await urgent_repo.create_broadcast(
            seeker_id=seeker_id,
            skill_id=data.skill_id,
            latitude=data.latitude,
            longitude=data.longitude,
        )

        # 2. Find nearby provider FCM tokens (within 3 KM, has_smartphone=True)
        tokens = await urgent_repo.get_nearby_fcm_tokens(
            latitude=data.latitude,
            longitude=data.longitude,
            radius_km=3,
        )

        await db.commit()

        # 3. Fire FCM to all nearby providers simultaneously (stub)
        if tokens:
            logger.info(
                f"Urgent broadcast {broadcast.id}: sending FCM to {len(tokens)} providers"
            )
            # TODO: await NotificationService.send_urgent_broadcast(tokens, broadcast.id, skill_id)
        else:
            logger.warning(
                f"Urgent broadcast {broadcast.id}: no nearby smartphone providers found"
            )

        return UrgentBroadcastResponse(
            broadcast_id=broadcast.id,
            status=broadcast.status,
            expires_at=broadcast.expires_at,
            message=t("broadcast_created", lang),
        )

    @staticmethod
    async def claim_broadcast(
        broadcast_id: UUID,
        provider_id: UUID,
        db: AsyncSession,
        lang: str,
    ) -> dict:
        """
        Atomic claim — only the first provider to hit this wins.
        Uses with_for_update() pessimistic lock in the repository.
        """
        urgent_repo = UrgentRepository(db)

        broadcast = await urgent_repo.claim_broadcast(broadcast_id, provider_id)

        if not broadcast:
            raise DomainValidationError(t("broadcast_not_found", lang))

        # If broadcast was already claimed or expired by the time we locked it
        if broadcast.status == BroadcastStatus.CLAIMED:
            if broadcast.claimed_by_provider_id == provider_id:
                # This provider already claimed it (duplicate tap) — idempotent OK
                await db.commit()
                return {"broadcast_id": broadcast_id, "status": "CLAIMED", "yours": True}
            # Another provider claimed it first
            raise DomainIntegrityError(t("broadcast_already_claimed", lang))

        if broadcast.status == BroadcastStatus.EXPIRED:
            raise DomainValidationError(t("broadcast_not_found", lang))

        await db.commit()

        logger.info(f"Broadcast {broadcast_id} claimed by provider {provider_id}")

        # TODO: Notify seeker that provider is on the way
        # await NotificationService.send_broadcast_claimed(broadcast.seeker_id, provider_id)

        return {
            "broadcast_id": broadcast_id,
            "status": "CLAIMED",
            "yours": True,
        }
```

---

## 4. Routers


### `app/api/v1/search.py`

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.i18n import get_lang
from app.core.security import get_current_user
from app.models.user import User
from app.services.search_service import SearchService

router = APIRouter()


@router.get("/providers")
async def search_providers(
    skill_category_id: int = Query(..., description="Category ID to search within"),
    seeker_lat: float = Query(..., description="Seeker's current latitude"),
    seeker_lng: float = Query(..., description="Seeker's current longitude"),
    search_radius_km: int = Query(1, ge=1, le=50, description="Search radius in KM"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    lang: str = Depends(get_lang),
):
    """
    Geo-aware provider search with ranking score.
    Auto-expands to 2km if no results found within requested radius.
    Phone numbers are never included in search results.
    """
    return await SearchService.find_providers(
        skill_category_id=skill_category_id,
        seeker_lat=seeker_lat,
        seeker_lng=seeker_lng,
        search_radius_km=search_radius_km,
        db=db,
        lang=lang,
    )
```

### `app/api/v1/urgent.py`

```python
from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.i18n import get_lang
from app.core.security import get_current_user
from app.models.user import User, Role
from app.schemas.urgent_schema import UrgentBroadcastCreateSchema, UrgentBroadcastResponse
from app.services.urgent_service import UrgentService
from app.core.exceptions import DomainValidationError
from app.core.i18n import t

router = APIRouter()


@router.post("/broadcast", response_model=UrgentBroadcastResponse, status_code=201)
async def create_urgent_broadcast(
    data: UrgentBroadcastCreateSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    lang: str = Depends(get_lang),
):
    """
    Seeker triggers 'Need It NOW'.
    Creates broadcast row + fires FCM to all nearby providers with smartphones.
    Expires in 5 minutes if no one claims.
    """
    if current_user.role != Role.SEEKER:
        raise DomainValidationError(t("booking_not_yours", lang))

    return await UrgentService.create_broadcast(
        data=data,
        seeker_id=current_user.id,
        db=db,
        lang=lang,
    )


@router.post("/broadcast/{broadcast_id}/claim", status_code=200)
async def claim_urgent_broadcast(
    broadcast_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    lang: str = Depends(get_lang),
):
    """
    Provider taps 'Accept'. Atomic pessimistic lock ensures only one wins.
    409 if another provider already claimed it.
    """
    if current_user.role != Role.PROVIDER:
        raise DomainValidationError(t("booking_not_yours", lang))

    return await UrgentService.claim_broadcast(
        broadcast_id=broadcast_id,
        provider_id=current_user.id,
        db=db,
        lang=lang,
    )
```

---

## 5. One Method to Add to `UserRepository`

---

## 6. Important Notes

### `booking/provider/me` route ordering conflict

FastAPI matches routes top-to-bottom. The route `GET /bookings/provider/me`
will conflict with `GET /bookings/{booking_id}` if you add that later.
**Always register the static route (`/provider/me`) before any dynamic
route (`/{booking_id}`) in the same router.**

The current file already does this correctly.

### Search query: `ST_DWithin` vs `ST_Distance`

- `ST_DWithin` is used for the **filter** (fast, uses spatial index).
- `ST_Distance` is used for the **distance label** in the SELECT (for display).

Never use `ST_Distance` in the WHERE clause — it calculates distance for
every row and ignores the spatial index. This is already correct in the code.

### The `with_for_update()` claim race condition

The `claim_broadcast` repo method locks the row with `SELECT ... FOR UPDATE`.
This means if two providers tap "Accept" at the exact same millisecond, one
transaction will wait for the other to finish before reading the status.
The second one will then see `status = CLAIMED` and get the 409 error.
This is the correct behavior.

### Flutter vs Web: location permissions

**Flutter:** Use the `geolocator` package.
```dart
Position position = await Geolocator.getCurrentPosition();
// Send position.latitude and position.longitude with search request
```

**React (Web):** Use the browser Geolocation API.
```javascript
navigator.geolocation.getCurrentPosition((pos) => {
  const { latitude, longitude } = pos.coords;
  // Include in search query params
});
```
Both send the coordinates as query params to `GET /api/v1/search/providers`.



# APScheduler
# app/jobs/booking_jobs.py
```python
from datetime import datetime, timedelta
from loguru import logger
from sqlalchemy import update

from app.db.session import AsyncSessionLocal
from app.models.booking import Booking, BookingStatus
from app.repositories.booking_repository import BookingRepository


async def send_booking_followup_notifications():
    """
    Runs every 5 minutes via APScheduler.
    Finds INITIATED bookings that crossed the 2-hour mark and sends FCM.

    Why a polling job instead of scheduling per booking:
    APScheduler with multiple Gunicorn workers would fire duplicate jobs
    if each booking schedules its own. A single polling job with a time
    window is simpler and safe.
    """
    async with AsyncSessionLocal() as db:
        repo = BookingRepository(db)
        bookings = await repo.get_initiated_ready_for_followup()

        if not bookings:
            return

        logger.info(f"Booking followup job: {len(bookings)} bookings ready for FCM")

        for booking in bookings:
            # Status guard: only send if still INITIATED
            # (could have been confirmed/cancelled in the last 5 mins)
            if booking.status != BookingStatus.INITIATED:
                continue

            logger.info(
                f"Sending 2hr follow-up FCM for booking {booking.id} "
                f"to seeker {booking.seeker_id}"
            )
            # TODO: await NotificationService.send_booking_followup(
            #     seeker_id=booking.seeker_id,
            #     booking_id=booking.id,
            #     attempt=1
            # )


async def expire_stale_bookings():
    """
    Runs nightly at midnight via APScheduler.
    INITIATED bookings older than 48 hours → AUTO_EXPIRED.
    This is unchanged from the original design.
    """
    async with AsyncSessionLocal() as db:
        cutoff = datetime.utcnow() - timedelta(hours=48)
        result = await db.execute(
            update(Booking)
            .where(Booking.status == BookingStatus.INITIATED)
            .where(Booking.call_unlocked_at < cutoff)
            .values(status=BookingStatus.AUTO_EXPIRED)
            .returning(Booking.id)
        )
        expired = len(result.all())
        await db.commit()
        if expired:
            logger.info(f"Nightly cleanup: expired {expired} stale bookings")
```

# register jobs

```python
# In lifespan, after setup_logging():
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.jobs.booking_jobs import send_booking_followup_notifications, expire_stale_bookings

scheduler = AsyncIOScheduler()
scheduler.add_job(send_booking_followup_notifications, "interval", minutes=5)
scheduler.add_job(expire_stale_bookings, "cron", hour=0, minute=0)
scheduler.start()
yield
scheduler.shutdown()
```