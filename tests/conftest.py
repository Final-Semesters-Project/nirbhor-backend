# shared fixtures (DB, client, test data)
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool, AsyncAdaptedQueuePool
from typing import AsyncGenerator
import pytest
import pytest_asyncio
from app.db.base import Base
from httpx import ASGITransport, AsyncClient
from app.db.session import get_db_session
from app.main import app
from sqlalchemy import text, update

from app.models.provider_profile_model import ProviderProfile


# ---------------- Test Database -------------------
# separate db from dev -> test will create and destroy db
TEST_DATABASE_URL = settings.DATABASE_URL.replace(
    settings.POSTGRES_DB, f"{settings.POSTGRES_DB}_test"
)

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    poolclass=NullPool,  # no pooling in tests — each test gets clean connection
)

TestSessionLocal = async_sessionmaker(
    test_engine,
    expire_on_commit=False,
    autocommit=False,
    autoflush=True
)


# ----- Session-scoped: create tables once, drop after all tests ---------
@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_database():
    """Creates all tables before tests, drops them after."""
    async with test_engine.begin() as conn:
        # 1. Enable PostGIS inside the fresh test database space first!
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))

        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ── Function-scoped: each test gets a rolled-back transaction ──────
@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Each test runs in a transaction that gets rolled back after.
    This means tests don't pollute each other's data.
    """
    async with test_engine.begin() as conn:
        # create a savepoint — we'll roll back to here after each test
        await conn.begin_nested()

        session = TestSessionLocal(bind=conn)
        try:
            yield session
        finally:
            await session.close()
            await conn.rollback()  # ← undo everything the test did


# ── Override FastAPI's DB dependency with test DB ──────────────────
@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    HTTP client that uses the test DB session.
    Requests go through your real FastAPI app but hit the test DB.
    """
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ── Reusable test data ─────────────────────────────────────────────
@pytest.fixture
def seeker_payload():
    return {
        "name_en": "Test Seeker",
        "name_bn": "টেস্ট সিকার",
        "phone": "01630956567",
        "password": "securepassword123",
    }


@pytest.fixture
def provider_payload():
    return {
        "name_en": "Test Provider",
        "name_bn": "টেস্ট প্রোভাইডার",
        "phone": "01730956568",
        "password": "securepassword123",
        "skill_ids": [1, 2, 3],        # empty until skill table has data
        "latitude": 23.8103,
        "longitude": 90.4125,
        "working_radius_km": 2,
        "has_smartphone": True,
    }


# add skills data
@pytest.fixture
async def seed_test_skills(db_session):
    """Inserts mock skills into the isolated test database."""
    # Ensure a category exists first if your skills table relies on a category foreign key
    await db_session.execute(
        text("INSERT INTO categories (id, name_en, name_bn) VALUES (1, 'Test Category', 'টেস্ট ক্যাটাগরি') ON CONFLICT DO NOTHING;")
    )

    # Insert mock skills matching your payload ids [1, 2, 3]
    for skill_id in [1, 2, 3]:
        await db_session.execute(
            text(
                f"INSERT INTO skills (id, category_id, name_en, name_bn) VALUES ({skill_id}, 1, 'Skill {skill_id}', 'দক্ষতা {skill_id}') ON CONFLICT DO NOTHING;")
        )

    await db_session.commit()


# get access
@pytest_asyncio.fixture
async def get_authenticated_provider_token(
    client: AsyncClient,
    db_session: AsyncSession,
    provider_payload: dict,
    seed_test_skills
) -> str:
    """
    Registers a fresh provider through the API, then returns access token for protected route testing.
    Also backdates location and radius update timestamps to allow immediate updates in tests.
    """
    PROVIDER_REG_URL = "/api/v1/auth/register/provider"

    # 1. Register the provider
    response = await client.post(PROVIDER_REG_URL, json=provider_payload)
    if response.status_code != 201:
        pytest.fail(f"Fixture failed to register provider: {response.text}")

    data = response.json()
    access_token = data["access_token"]
    user_id = data["user_id"]

    # 2. Backdate the update timestamps to bypass the 7-day restriction
    # Set them to 8 days ago so tests can update immediately
    past_date = datetime.now(timezone.utc) - timedelta(days=8)

    await db_session.execute(
        update(ProviderProfile)
        .where(ProviderProfile.user_id == user_id)
        .values(
            location_updated_at=past_date,
            radius_updated_at=past_date
        )
    )
    await db_session.commit()

    return access_token
