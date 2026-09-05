```python
# tests/conftest.py
import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from geoalchemy2.shape import from_shape
from shapely.geometry import Point

from app.main import app
from app.db.session import get_db_session
from app.models.user_model import User, Role
from app.models.provider_profile_model import ProviderProfile, VerificationLevel, VerificationStatus
from app.models.booking_model import Booking, BookingStatus
from app.models.skill_model import Skill
from app.models.category_model import Category
from app.models.provider_skill_link_model import ProviderSkillLink
from app.core.security import Security

TEST_DATABASE_URL = "postgresql+asyncpg://postgres:password@localhost:5432/nirbhor_test"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)


@pytest_asyncio.fixture
async def db():
    """
    SAVEPOINT-nested transaction pattern.

    Why this exists: the service layer calls db.commit(). A plain
    session.rollback() at teardown does NOTHING once commit() has been
    called, because commit() already ended the transaction - there's
    nothing left to roll back, and the rows are permanently in
    nirbhor_test. That causes cross-test pollution (e.g. a phone number
    inserted in test A collides with test B's "duplicate phone" check
    for the wrong reason, or a leftover row silently satisfies an
    assertion it shouldn't).

    Fix: open an outer transaction on the raw connection, bind the
    session to that connection, and open a SAVEPOINT inside it. When the
    app calls session.commit(), SQLAlchemy only commits the SAVEPOINT
    (because the session is bound to a connection already inside a
    transaction) - the outer transaction stays open. We restart a new
    SAVEPOINT every time one ends (via the after_transaction_end event),
    so repeated commit() calls within one test still work. At teardown
    we roll back the OUTER transaction, which discards everything no
    matter how many times the app committed.
    """
    async with test_engine.connect() as conn:
        outer_txn = await conn.begin()

        session = AsyncSession(bind=conn, expire_on_commit=False)
        nested = await conn.begin_nested()

        @event.listens_for(session.sync_session, "after_transaction_end")
        def _restart_savepoint(sync_session, transaction):
            nonlocal nested
            if not nested.is_active:
                nested = conn.sync_connection.begin_nested()

        try:
            yield session
        finally:
            await session.close()
            if outer_txn.is_active:
                await outer_txn.rollback()


@pytest_asyncio.fixture
async def client(db):
    async def override_get_db():
        yield db

    app.dependency_overrides[get_db_session] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as c:
        yield c

    app.dependency_overrides.clear()
```

```python
# tests/test_auth/test_registration.py

import pytest
from httpx import AsyncClient

SEEKER_REGISTER_URL = "/api/v1/auth/register/seeker"
PROVIDER_REGISTER_URL = "/api/v1/auth/register/provider"


class TestSeekerRegistration:
    @pytest.mark.asyncio
    async def test_seeker_registration_success(self, client: AsyncClient):
    payload = {
        "name_en": "Rahim",
        "name_bn": "রহিম",
        "phone": "01712345678",
        "password": "pass1234",
    }
    response = await client.post(SEEKER_REGISTER_URL, json=payload)

    assert response.status_code == 201, response.text
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["role"] == "seeker"
    assert "user_id" in data
    # password must never appear anywhere in the response
    assert "password" not in data
    assert "password_hash" not in data

    @pytest.mark.asyncio
    async def test_seeker_duplicate_phone_returns_409(self, client: AsyncClient, seeker_user):
        payload = {
            "name_en": "Another Name",
            "name_bn": "অন্য নাম",
            "phone": seeker_user.phone_en,  # collides with fixture
            "password": "pass1234",
        }
        response = await client.post(SEEKER_REGISTER_URL, json=payload)
        assert response.status_code == 409, response.text

    @pytest.mark.asyncio
    async def test_seeker_missing_name_returns_422(self, client: AsyncClient):
        payload = {
            "name_bn": "রহিম",
            "phone": "01712345679",
            "password": "pass1234",
        }
        response = await client.post(SEEKER_REGISTER_URL, json=payload)
        assert response.status_code == 422, response.text


class TestProviderRegistration:

    @pytest.mark.asyncio
    async def test_provider_registration_success(self, client: AsyncClient, skill):
        payload = {
            "name_en": "Karim",
            "name_bn": "করিম",
            "phone": "01812345678",
            "password": "pass1234",
            "skill_ids": [skill.id],
            "latitude": 23.7510,
            "longitude": 90.3930,
            "working_radius_km": 5,
            "has_smartphone": True,
        }
        response = await client.post(PROVIDER_REGISTER_URL, json=payload)

        assert response.status_code == 201, response.text
        data = response.json()
        assert data["role"] == "provider"

    @pytest.mark.asyncio
    async def test_provider_empty_skill_ids_returns_400(self, client: AsyncClient):
    """
    skill_ids: list[int] has no Pydantic-level min-length constraint, so [] passes
    schema validation — the rejection happens in the service layer
    (`if len(data.skill_ids) == 0: raise HTTPException(400, ...)`), not Pydantic.
    """
    payload = {
        "name_en": "Karim",
        "name_bn": "করিম",
        "phone": "01812345679",
        "password": "pass1234",
        "preferred_lang": "en",
        "skill_ids": [],
        "latitude": 23.7510,
        "longitude": 90.3930,
        "working_radius_km": 5,
        "has_smartphone": True,
    }
    response = await client.post(PROVIDER_REGISTER_URL, json=payload)
    assert response.status_code == 400, response.text

    @pytest.mark.asyncio
    async def test_provider_invalid_skill_ids_returns_400(self, client: AsyncClient):
        payload = {
            "name_en": "Karim",
            "name_bn": "করিম",
            "phone": "01812345680",
            "password": "pass1234",
            "skill_ids": [99999],  # does not exist
            "latitude": 23.7510,
            "longitude": 90.3930,
            "working_radius_km": 5,
            "has_smartphone": True,
        }
        response = await client.post(PROVIDER_REGISTER_URL, json=payload)
        assert response.status_code == 400, response.text

    @pytest.mark.asyncio
    async def test_provider_missing_smartphone_flag_returns_422(self, client: AsyncClient, skill):
        payload = {
            "name_en": "Karim",
            "name_bn": "করিম",
            "phone": "01812345681",
            "password": "pass1234",
            "skill_ids": [skill.id],
            "latitude": 23.7510,
            "longitude": 90.3930,
            "working_radius_km": 5,
            # has_smartphone intentionally omitted
        }
        response = await client.post(PROVIDER_REGISTER_URL, json=payload)
        assert response.status_code == 422, response.text
```

```python
# tests/test_auth/test_login.py

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.models.user_model import User

LOGIN_URL = "/api/v1/auth/login"


class TestLogin:

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient, seeker_user):
        response = await client.post(
            LOGIN_URL,
            json={"phone": seeker_user.phone_en, "password": "password123"},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    @pytest.mark.asyncio
    async def test_login_wrong_password_returns_401(self, client: AsyncClient, seeker_user):
        response = await client.post(
            LOGIN_URL,
            json={"phone": seeker_user.phone_en, "password": "wrong-password"},
        )
        assert response.status_code == 401, response.text

    @pytest.mark.asyncio
    async def test_login_nonexistent_phone_returns_401(self, client: AsyncClient):
        response = await client.post(
            LOGIN_URL,
            json={"phone": "01700000000", "password": "whatever123"},
        )
        assert response.status_code == 401, response.text

    @pytest.mark.asyncio
    async def test_login_suspended_account_returns_401(self, client: AsyncClient, db, seeker_user):
        await db.execute(
            update(User).where(User.id == seeker_user.id).values(is_active=False)
        )
        await db.flush()

        response = await client.post(
            LOGIN_URL,
            json={"phone": seeker_user.phone_en, "password": "password123"},
        )
        assert response.status_code == 401, response.text
```

```python
# tests/test_auth/test_logout.py

import pytest
from httpx import AsyncClient

LOGOUT_URL = "/api/v1/auth/logout"
# pick any authenticated endpoint to prove the token is blocked after logout
PROTECTED_URL = "/api/v1/bookings/seeker/me"


class TestLogout:

    @pytest.mark.asyncio
    async def test_logout_success(self, client: AsyncClient, seeker_headers):
        response = await client.post(LOGOUT_URL, headers=seeker_headers)
        assert response.status_code == 200, response.text
        assert "message" in response.json()

    @pytest.mark.asyncio
    async def test_logout_token_blocked(self, client: AsyncClient, seeker_headers):
        logout_resp = await client.post(LOGOUT_URL, headers=seeker_headers)
        assert logout_resp.status_code == 200

        reuse_resp = await client.get(PROTECTED_URL, headers=seeker_headers)
        assert reuse_resp.status_code == 401, reuse_resp.text

    @pytest.mark.asyncio
    async def test_logout_without_token_returns_401(self, client: AsyncClient):
        response = await client.post(LOGOUT_URL)
        assert response.status_code == 401, response.text
```
