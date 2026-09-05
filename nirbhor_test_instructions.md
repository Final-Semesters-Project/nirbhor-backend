# Nirbhor Backend — Pytest Test Instructions for New Claude Chat

## Context to give the new Claude

Say this at the start:
> "I am building Nirbhor — a Bengali-language hyperlocal labor marketplace.
> Backend: FastAPI + SQLAlchemy 2.0 async + PostgreSQL + PostGIS.
> I need pytest tests. Tests insert data into a real test DB and delete it after.
> No mocking of DB. Mock only external services (FCM, Cloudinary, Anthropic).
> I use pytest-asyncio, httpx AsyncClient, and SQLAlchemy async sessions.
> Read my conftest.py and test setup below, then write tests."

---

## Project Structure

```
app/
  models/
    user_model.py
    provider_profile_model.py
    booking_model.py
    review_model.py
    urgent_broadcast_model.py
    fcm_token_model.py
    user_session_model.py
    skill_model.py
    category_model.py
    provider_skill_link_model.py
    user_report_model.py
    team_model.py
    provider_skill_link_model.py
    app_version_model.py
  api/v1/
    auth_router.py         → /api/v1/auth/
    bookings_router.py     → /api/v1/bookings/
    search_router.py       → /api/v1/search/
    urgent_router.py       → /api/v1/urgentBroadcast/
    reviews_router.py      → /api/v1/reviews/
    provider_router.py     → /api/v1/provider/
    admin_router.py        → /api/v1/admin/
    categories_router.py   → /api/v1/category/
    skill_router.py        → /api/v1/skill/
    uploads_router.py       → /api/v1/uploads/
    user_router.py         → /api/v1/users/
tests/
  conftest.py
  test_auth/
    test_registration.py
    test_login.py
    test_logout.py
  test_bookings/
    test_initiate.py
    test_respond.py
    test_complete.py
    test_history.py
  test_search/
    test_provider_search.py
  test_urgent/
    test_broadcast.py
    test_claim.py
  test_reviews/
    test_create_review.py
  test_provider/
    test_dashboard.py
    test_update_profile.py
    test_skills.py
  test_admin/
    test_dashboard.py
    test_verifications.py
    test_reports.py
    test_users.py
    test_analytics.py
```

---

## Database Tables and Fields

### users
```python
id: UUID (PK)
phone_en: str (unique)           # e.g. "01711111111"
password_hash: str
role: Enum                       # "seeker", "provider", "admin"
is_active: bool (default True)
created_at: datetime
last_active_at: datetime
name_en: str
name_bn: str
preferred_lang: str              # "en" or "bn"
firebase_uid: str | None
google_email: str | None
```

### provider_profiles
```python
user_id: UUID (PK, FK → users)
photo_url: str | None
photo_public_id: str | None
nid_url_front: str | None
nid_front_public_id: str | None
nid_url_back: str | None
nid_back_public_id: str | None
verification_level: Enum         # "basic", "verified", "trusted"
verification_status: Enum        # "not_initiated", "pending", "approved", "rejected"
verification_rejection_reason: str | None
base_location: Geometry(POINT)  # PostGIS, srid=4326
location_updated_at: datetime
working_radius_km: int
radius_updated_at: datetime
has_smartphone: bool
ai_review_summary_en: str | None
ai_review_summary_bn: str | None
ai_summary_generated_at: datetime | None
average_rating: float | None
warning_status: bool (default False)
is_available: bool
```

### categories
```python
id: int (PK)
name_en: str                    # "Home Repairs"
name_bn: str                    # "বাসা মেরামত"
```

### skills
```python
id: int (PK)
category_id: int (FK → categories)
name_en: str                    # "Electrician"
name_bn: str                    # "ইলেকট্রিশিয়ান"
```

### provider_skill_links
```python
provider_id: UUID (FK → provider_profiles)
skill_id: int (FK → skills)
```

### fcm_tokens
```python
id: UUID (PK)
user_id: UUID (FK → users)
token: str (unique)
device_type: Enum               # "android", "ios", "web"
```

### bookings
```python
id: UUID (PK)
seeker_id: UUID (FK → users)
provider_id: UUID (FK → users)
skill_id: int (FK → skills)
status: Enum                    # "initiated", "in_progress", "completed",
                                #  "cancelled", "auto_expired"
call_unlocked_at: datetime
confirmed_at: datetime | None
work_schedule: datetime | None
completed_at: datetime | None
created_at: datetime
job_location: Geometry(POINT)   # PostGIS, srid=4326
team_id: UUID | None
```

### reviews
```python
id: UUID (PK)
booking_id: UUID (FK → bookings)
reviewer_id: UUID (FK → users)
reviewee_id: UUID (FK → users)
rating: int                     # 1-5
comment: str | None
is_anonymous: bool (default True)
created_at: datetime
# UniqueConstraint: (booking_id, reviewer_id)
# CheckConstraint: rating >= 1 AND rating <= 5
```

### urgent_broadcasts
```python
id: UUID (PK)
seeker_id: UUID (FK → users)
skill_id: int (FK → skills)
location: Geometry(POINT)       # PostGIS, srid=4326
status: Enum                    # "broadcasting", "claimed", "expired"
claimed_by_provider_id: UUID | None (FK → users)
expires_at: datetime
```

### user_sessions
```python
id: UUID (PK)
user_id: UUID (FK → users)
refresh_token: str
device_info: str
expires_at: datetime
```

### user_reports
```python
id: UUID (PK)
reporter_id: UUID (FK → users)
reported_user_id: UUID (FK → users)
booking_id: UUID | None (FK → bookings)
reason: str
status: Enum                    # "pending", "under_investigation",
                                #  "reviewed", "action_taken"
```

---

## conftest.py — give this to Claude exactly

```python
# tests/conftest.py

import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from geoalchemy2.shape import from_shape
from shapely.geometry import Point

from app.main import app
from app.db.session import get_db_session
from app.models.user_model import User, Role
from app.models.provider_profile_model import ProviderProfile, VerificationLevel, VerificationStatus
from app.models.booking_model import Booking, BookingStatus
from app.models.review_model import Review
from app.models.urgent_broadcast_model import UrgentBroadcast, BroadcastStatus
from app.models.fcm_token_model import FCMToken, DeviceType
from app.models.user_session_model import UserSession
from app.models.skill_model import Skill
from app.models.category_model import Category
from app.models.provider_skill_link_model import ProviderSkillLink
from app.core.security import Security

# ── Use your local test database ───────────────────────────────────────────────
# Set this in .env.test or hardcode for local dev only
TEST_DATABASE_URL = "postgresql+asyncpg://postgres:password@localhost:5432/nirbhor_test"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db():
    """Provides a test DB session. Rolls back after each test."""
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db):
    """
    AsyncClient with the test DB session injected.
    All requests go through FastAPI with the real test DB.
    """
    async def override_get_db():
        yield db

    app.dependency_overrides[get_db_session] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as c:
        yield c

    app.dependency_overrides.clear()


# ── Helper: create a point for PostGIS ────────────────────────────────────────
def make_point(lng: float = 90.3930, lat: float = 23.7510):
    return from_shape(Point(lng, lat), srid=4326)


# ── User fixtures ──────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def seeker_user(db):
    user = User(
        id=uuid4(),
        phone_en="01711000001",
        password_hash=Security.hash_password("password123"),
        role=Role.SEEKER,
        name_en="Test Seeker",
        name_bn="টেস্ট সিকার",
        preferred_lang="en",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        last_active_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def provider_user(db):
    user = User(
        id=uuid4(),
        phone_en="01811000001",
        password_hash=Security.hash_password("password123"),
        role=Role.PROVIDER,
        name_en="Test Provider",
        name_bn="টেস্ট প্রোভাইডার",
        preferred_lang="bn",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        last_active_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def admin_user(db):
    user = User(
        id=uuid4(),
        phone_en="01911000001",
        password_hash=Security.hash_password("admin123"),
        role=Role.ADMIN,
        name_en="Admin User",
        name_bn="অ্যাডমিন",
        preferred_lang="en",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        last_active_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def provider_profile(db, provider_user):
    profile = ProviderProfile(
        user_id=provider_user.id,
        base_location=make_point(90.3930, 23.7510),
        location_updated_at=datetime.now(timezone.utc) - timedelta(days=20),
        working_radius_km=5,
        radius_updated_at=datetime.now(timezone.utc) - timedelta(days=20),
        has_smartphone=True,
        is_available=True,
        verification_level=VerificationLevel.BASIC,
        verification_status=VerificationStatus.NOT_INITIATED,
        warning_status=False,
    )
    db.add(profile)
    await db.flush()
    return profile


@pytest_asyncio.fixture
async def category(db):
    cat = Category(name_en="Home Repairs", name_bn="বাসা মেরামত")
    db.add(cat)
    await db.flush()
    return cat


@pytest_asyncio.fixture
async def skill(db, category):
    s = Skill(category_id=category.id, name_en="Electrician", name_bn="ইলেকট্রিশিয়ান")
    db.add(s)
    await db.flush()
    return s


@pytest_asyncio.fixture
async def provider_with_skill(db, provider_profile, skill):
    link = ProviderSkillLink(
        provider_id=provider_profile.user_id,
        skill_id=skill.id,
    )
    db.add(link)
    await db.flush()
    return provider_profile


@pytest_asyncio.fixture
async def initiated_booking(db, seeker_user, provider_user, skill):
    booking = Booking(
        id=uuid4(),
        seeker_id=seeker_user.id,
        provider_id=provider_user.id,
        skill_id=skill.id,
        status=BookingStatus.INITIATED,
        call_unlocked_at=datetime.now(timezone.utc),
        job_location=make_point(),
        created_at=datetime.now(timezone.utc),
    )
    db.add(booking)
    await db.flush()
    return booking


@pytest_asyncio.fixture
async def completed_booking(db, seeker_user, provider_user, skill):
    booking = Booking(
        id=uuid4(),
        seeker_id=seeker_user.id,
        provider_id=provider_user.id,
        skill_id=skill.id,
        status=BookingStatus.COMPLETED,
        call_unlocked_at=datetime.now(timezone.utc) - timedelta(hours=5),
        confirmed_at=datetime.now(timezone.utc) - timedelta(hours=4),
        work_schedule=datetime.now(timezone.utc) - timedelta(hours=2),
        completed_at=datetime.now(timezone.utc) - timedelta(hours=1),
        job_location=make_point(),
        created_at=datetime.now(timezone.utc) - timedelta(hours=5),
    )
    db.add(booking)
    await db.flush()
    return booking


# ── Auth headers helpers ───────────────────────────────────────────────────────

def auth_headers(user: User) -> dict:
    """Generate Bearer token headers for a user."""
    from app.core.security import Security
    token = Security.create_access_token({"sub": str(user.id), "role": user.role.value})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def seeker_headers(seeker_user):
    return auth_headers(seeker_user)


@pytest_asyncio.fixture
async def provider_headers(provider_user):
    return auth_headers(provider_user)


@pytest_asyncio.fixture
async def admin_headers(admin_user):
    return auth_headers(admin_user)
```

---

## All Tests to Write

### GROUP 1: Authentication — `tests/test_auth/`

#### `test_registration.py`

| Test name | Method | URL | What to test |
|-----------|--------|-----|-------------|
| `test_seeker_registration_success` | POST | `/api/v1/auth/register/seeker` | Returns 201, access_token present, role=seeker |
| `test_seeker_duplicate_phone_returns_409` | POST | `/api/v1/auth/register/seeker` | Same phone twice → 409 |
| `test_seeker_missing_name_returns_422` | POST | `/api/v1/auth/register/seeker` | Missing name_en → 422 |
| `test_provider_registration_success` | POST | `/api/v1/auth/register/provider` | Returns 201, role=provider |
| `test_provider_missing_skill_ids_returns_422` | POST | `/api/v1/auth/register/provider` | Empty skill_ids → 422 |
| `test_provider_invalid_skill_ids_returns_400` | POST | `/api/v1/auth/register/provider` | skill_ids=[99999] → 400 |
| `test_provider_missing_smartphone_flag_returns_422` | POST | `/api/v1/auth/register/provider` | No has_smartphone → 422 |

**Payload for seeker:**
```python
{"name_en": "Rahim", "name_bn": "রহিম", "phone": "01712345678", "password": "pass1234"}
```
**Payload for provider:**
```python
{
  "name_en": "Karim", "name_bn": "করিম", "phone": "01812345678",
  "password": "pass1234", "skill_ids": [skill.id],
  "latitude": 23.7510, "longitude": 90.3930,
  "working_radius_km": 5, "has_smartphone": True
}
```

#### `test_login.py`

| Test name | What to test |
|-----------|-------------|
| `test_login_success` | Returns 200, both tokens present |
| `test_login_wrong_password_returns_401` | Wrong password → 401 |
| `test_login_nonexistent_phone_returns_401` | Unknown phone → 401 |
| `test_login_suspended_account_returns_401` | is_active=False → 401 |

#### `test_logout.py`

| Test name | What to test |
|-----------|-------------|
| `test_logout_success` | Returns 200, message present |
| `test_logout_token_blocked` | After logout, same token rejected on next request → 401 |
| `test_logout_without_token_returns_401` | No auth header → 401 |

---

### GROUP 2: Bookings — `tests/test_bookings/`

#### `test_initiate.py`

| Test name | URL | What to test |
|-----------|-----|-------------|
| `test_initiate_booking_success` | POST `/api/v1/bookings/initiate` | Returns 201, provider_phone revealed |
| `test_initiate_returns_provider_phone` | POST `/api/v1/bookings/initiate` | Response contains provider_phone |
| `test_initiate_exceeds_max_open_bookings_returns_409` | POST `/api/v1/bookings/initiate` | Already has INITIATED booking → 409 |
| `test_initiate_provider_not_found_returns_400` | POST `/api/v1/bookings/initiate` | Invalid provider_id → 400 |
| `test_initiate_requires_seeker_role` | POST `/api/v1/bookings/initiate` | Provider trying to initiate → 400/403 |

**Payload:**
```python
{
  "provider_id": str(provider_user.id),
  "skill_id": skill.id,
  "latitude": 23.7510,
  "longitude": 90.3930
}
```

#### `test_respond.py`

| Test name | What to test |
|-----------|-------------|
| `test_respond_hired_true_sets_in_progress` | hired=True → status becomes in_progress |
| `test_respond_hired_true_requires_work_schedule` | hired=True, no work_schedule → 422 |
| `test_respond_hired_true_past_work_schedule_returns_422` | work_schedule in past → 422 |
| `test_respond_hired_false_sets_cancelled` | hired=False → status becomes cancelled |
| `test_respond_wrong_booking_returns_400` | Non-existent booking_id → 400 |
| `test_respond_not_own_booking_returns_400` | Different seeker trying to respond → 400 |
| `test_respond_already_in_progress_returns_400` | Booking already IN_PROGRESS → 400 |

**URL:** `PATCH /api/v1/bookings/{booking_id}/respond`
**Payload:** `{"hired": true, "work_schedule": "2026-12-01T10:00:00+00:00"}`

#### `test_complete.py`

| Test name | What to test |
|-----------|-------------|
| `test_mark_completed_success` | IN_PROGRESS → COMPLETED |
| `test_mark_completed_wrong_status_returns_400` | INITIATED booking → 400 |
| `test_mark_completed_not_own_booking_returns_400` | Different seeker → 400 |

**URL:** `PATCH /api/v1/bookings/{booking_id}/complete`

#### `test_history.py`

| Test name | What to test |
|-----------|-------------|
| `test_seeker_history_returns_list` | GET `/api/v1/bookings/seeker/me` → list |
| `test_seeker_history_pagination` | page=1&page_size=2 → correct pagination metadata |
| `test_seeker_history_only_own_bookings` | Seeker only sees their own bookings |
| `test_provider_incoming_only_in_progress` | GET `/api/v1/bookings/provider/me` → only IN_PROGRESS |
| `test_active_booking_check` | GET `/api/v1/bookings/seeker/last_active_initiated` → has_active_booking |

---

### GROUP 3: Search — `tests/test_search/`

#### `test_provider_search.py`

| Test name | What to test |
|-----------|-------------|
| `test_search_finds_nearby_provider` | Provider at 0.4km returns in results |
| `test_search_excludes_unavailable_provider` | is_available=False → not in results |
| `test_search_excludes_inactive_user` | is_active=False → not in results |
| `test_search_excludes_60_day_inactive` | last_active_at 61 days ago → not in results |
| `test_search_auto_expands_radius` | No results at 1km → auto-expands, expanded_radius=True |
| `test_search_response_excludes_phone` | provider_phone NOT in any result item |
| `test_search_requires_auth` | No token → 401 |

**URL:** `GET /api/v1/search/providers?skill_id={id}&seeker_lat=23.7510&seeker_lng=90.3930&search_radius_km=1`

**Setup:** Create provider at ~0.4km from seeker point using `make_point(90.3950, 23.7540)` and `working_radius_km=2`.

---

### GROUP 4: Urgent Broadcasts — `tests/test_urgent/`

#### `test_broadcast.py`

| Test name | What to test |
|-----------|-------------|
| `test_create_broadcast_success` | Returns 201, status=broadcasting, expires_at present |
| `test_create_broadcast_invalid_skill_returns_400` | skill_id=99999 → 400 |
| `test_create_broadcast_requires_seeker_role` | Provider creating broadcast → error |
| `test_broadcast_status_broadcasting` | GET `/api/v1/urgentBroadcast/broadcast/{id}/status` → status=broadcasting |
| `test_broadcast_status_seconds_remaining` | seconds_remaining > 0 and <= 300 |
| `test_broadcast_detail_returns_skill_name` | GET `/api/v1/urgentBroadcast/broadcast/{id}` → skill_name present |

#### `test_claim.py`

| Test name | What to test |
|-----------|-------------|
| `test_claim_broadcast_success` | First provider claims → 200, seeker_phone revealed |
| `test_claim_already_claimed_returns_409` | Second claim → 409 |
| `test_claim_expired_broadcast_returns_400` | expires_at in past, status=EXPIRED → 400 |
| `test_claim_nonexistent_broadcast_returns_400` | Random UUID → 400 |
| `test_claim_requires_provider_role` | Seeker trying to claim → error |

---

### GROUP 5: Reviews — `tests/test_reviews/`

#### `test_create_review.py`

| Test name | What to test |
|-----------|-------------|
| `test_create_review_success` | Returns 201, rating and comment present |
| `test_review_updates_provider_average_rating` | After review, provider_profile.average_rating updated |
| `test_review_not_eligible_returns_400` | Booking not COMPLETED → 400 |
| `test_review_duplicate_returns_409` | Second review same booking → 409 |
| `test_review_rating_below_1_returns_422` | rating=0 → 422 |
| `test_review_rating_above_5_returns_422` | rating=6 → 422 |
| `test_review_not_party_to_booking_returns_400` | Third party tries to review → 400 |

**Payload:** `{"booking_id": str(completed_booking.id), "rating": 5, "comment": "Great work", "is_anonymous": False}`

---

### GROUP 6: Provider — `tests/test_provider/`

#### `test_dashboard.py`

| Test name | What to test |
|-----------|-------------|
| `test_get_dashboard_success` | Returns 200, required fields present |
| `test_dashboard_requires_provider_role` | Seeker → error |
| `test_dashboard_returns_skills_list` | skills array in response |

**URL:** `GET /api/v1/provider/dashboard`
**Required response fields:** user_id, name, verification_level, is_available, working_radius_km, skills

#### `test_update_profile.py`

| Test name | What to test |
|-----------|-------------|
| `test_update_availability_toggle` | is_available=False → 200 |
| `test_update_working_radius` | working_radius_km=10 → 200 |
| `test_update_location` | latitude/longitude → 200, location_updated_at updated |
| `test_update_location_too_soon_returns_400` | location_updated_at < 7 days ago → 400 |
| `test_update_nid_sets_pending_when_all_three_uploaded` | After uploading all 3 photos → verification_status=pending |
| `test_update_nid_blocked_when_pending` | verification_status=pending → cannot re-upload → 400 |
| `test_update_nid_blocked_when_approved` | verification_status=approved → cannot re-upload → 400 |

#### `test_skills.py`

| Test name | What to test |
|-----------|-------------|
| `test_add_skill_success` | POST `/api/v1/provider/me/add_skill` → 200 |
| `test_add_invalid_skill_returns_400` | skill_id=99999 → 400 |
| `test_remove_skill_success` | DELETE `/api/v1/provider/me/remove_skill?skill_id={id}` → 200 |
| `test_remove_nonexistent_skill_returns_400` | Remove skill not linked → 400 |

---

### GROUP 7: Admin — `tests/test_admin/`

#### `test_dashboard.py`

| Test name | What to test |
|-----------|-------------|
| `test_admin_dashboard_success` | Returns 200, all count fields present |
| `test_admin_dashboard_requires_admin_role` | Seeker → 403 |
| `test_dashboard_counts_correct` | total_users matches actual DB count |

**URL:** `GET /api/v1/admin/dashboard`
**Required fields:** total_users, total_providers, total_seekers, total_bookings, pending_verifications, pending_reports, active_providers_today

#### `test_verifications.py`

| Test name | What to test |
|-----------|-------------|
| `test_list_pending_verifications` | Returns list of providers with pending status |
| `test_approve_verification` | PATCH approve → verification_status=approved, level=verified |
| `test_reject_verification` | PATCH reject with reason → verification_status=rejected |
| `test_reject_without_reason_returns_400` | action=reject, no reason → 400 |

#### `test_reports.py`

| Test name | What to test |
|-----------|-------------|
| `test_list_reports` | Returns list |
| `test_list_reports_filter_by_status` | ?status=PENDING → only pending |
| `test_dismiss_report` | action=dismiss → status=reviewed |
| `test_suspend_user_via_report` | action=suspend → reported user is_active=False |

#### `test_users.py`

| Test name | What to test |
|-----------|-------------|
| `test_list_all_users` | Returns paginated list |
| `test_filter_by_role` | ?role=PROVIDER → only providers |
| `test_get_user_detail` | GET `/{user_id}` → has total_bookings |
| `test_toggle_user_active` | PATCH toggle → is_active flips |

#### `test_analytics.py`

| Test name | What to test |
|-----------|-------------|
| `test_analytics_success` | Returns 200, all fields present |
| `test_analytics_bookings_per_week_is_list` | bookings_per_week is a list |
| `test_analytics_ratio_calculated` | seeker_to_provider_ratio is float |

---

## Test Setup Rules

### 1. Never mock the DB
All DB operations use the real test database. Only mock external services:
```python
# Mock FCM
with patch("app.services.notification_service.messaging.send"):
    ...

# Mock Cloudinary
with patch("app.core.cloudinary_helpers.cloudinary.uploader.destroy"):
    ...

# Mock Anthropic
with patch("app.jobs.ai_summary_job._call_anthropic", return_value=("summary en", "summary bn")):
    ...
```

### 2. Transaction rollback pattern
Each test gets a session that rolls back after the test. Data inserted in a test fixture is NOT committed to the DB — it lives only in the transaction and disappears after the test.

### 3. PostGIS location helper
```python
from geoalchemy2.shape import from_shape
from shapely.geometry import Point

def make_point(lng=90.3930, lat=23.7510):
    return from_shape(Point(lng, lat), srid=4326)

# Provider 0.4km away from default seeker point:
nearby_point = make_point(90.3950, 23.7540)

# Provider 7km away (outside range):
far_point = make_point(90.4350, 23.8050)
```

### 4. Install requirements
```
pip install pytest pytest-asyncio httpx sqlalchemy[asyncio] asyncpg geoalchemy2 shapely
```

### 5. pytest.ini
```ini
[pytest]
asyncio_mode = auto
```

### 6. Running tests
```bash
# All tests
pytest tests/ -v

# One group
pytest tests/test_auth/ -v

# One file
pytest tests/test_bookings/test_initiate.py -v

# With coverage
pytest tests/ --cov=app --cov-report=html
```

---

## Code Template for a Test File

```python
# tests/test_bookings/test_initiate.py

import pytest
from httpx import AsyncClient
from unittest.mock import patch
from uuid import uuid4


INITIATE_URL = "/api/v1/bookings/initiate"


class TestBookingInitiate:

    @pytest.mark.asyncio
    async def test_initiate_booking_success(
        self,
        client: AsyncClient,
        seeker_headers: dict,
        provider_user,
        provider_profile,   # ensures profile exists
        skill,
    ):
        payload = {
            "provider_id": str(provider_user.id),
            "skill_id": skill.id,
            "latitude": 23.7510,
            "longitude": 90.3930,
        }
        response = await client.post(
            INITIATE_URL,
            json=payload,
            headers=seeker_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert "booking_id" in data
        assert "provider_phone" in data
        assert data["provider_phone"] == provider_user.phone_en
        assert data["status"] == "initiated"

    @pytest.mark.asyncio
    async def test_initiate_requires_auth(self, client: AsyncClient, provider_user, skill):
        response = await client.post(
            INITIATE_URL,
            json={
                "provider_id": str(provider_user.id),
                "skill_id": skill.id,
                "latitude": 23.7510,
                "longitude": 90.3930,
            },
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_initiate_invalid_provider_returns_400(
        self,
        client: AsyncClient,
        seeker_headers: dict,
        skill,
    ):
        payload = {
            "provider_id": str(uuid4()),   # random UUID, doesn't exist
            "skill_id": skill.id,
            "latitude": 23.7510,
            "longitude": 90.3930,
        }
        response = await client.post(INITIATE_URL, json=payload, headers=seeker_headers)
        assert response.status_code in (400, 404)
```
