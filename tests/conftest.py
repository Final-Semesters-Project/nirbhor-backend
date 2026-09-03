from datetime import datetime, timezone
import os
from uuid import uuid4
from app.core.config import settings
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from app.core.security import Security
from app.db.session import get_db_session
from app.main import app
from sqlalchemy import event
import subprocess
from app.models.category_model import Category
from app.models.skill_model import Skill
from app.models.user_model import Role, User


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



@pytest_asyncio.fixture(scope="session", autouse=True)
async def _apply_migrations():
    """
    Runs real Alembic migrations against the test DB before the test session starts.
    This is deliberately NOT Base.metadata.create_all() — using the actual migration
    chain means a broken/inconsistent migration will fail tests too, not just broken
    models. Requires alembic's env.py to read DATABASE_URL from the environment.
    """
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        env={**os.environ, "DATABASE_URL": TEST_DATABASE_URL},
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.exit(
            f"Alembic migration failed against test DB:\n{result.stdout}\n{result.stderr}"
        )
    yield

# Run this two commands to create the test database:
# 1. docker exec -it nirbhor_db_dev_with_postgis psql -U postgres -c "CREATE DATABASE nirbhor_db_test;"
# 2. docker exec -it nirbhor_db_dev_with_postgis psql -U postgres -d nirbhor_db_test -c "CREATE EXTENSION IF NOT EXISTS postgis;"
# 3. docker exec -it nirbhor_backend_dev bash -c "DATABASE_URL=postgresql+asyncpg://postgres:local_password@db:5432/nirbhor_db_test alembic upgrade head"

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
                assert conn.sync_connection is not None
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

from geoalchemy2.shape import from_shape
from shapely.geometry import Point

def make_point(lng: float = 90.3930, lat: float = 23.7510):
    return from_shape(Point(lng, lat), srid=4326)

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

# ----- Session-scoped: create tables once, drop after all tests ---------
# @pytest_asyncio.fixture(scope="session", autouse=True)
# async def setup_test_database():
#     """Creates all tables before tests, drops them after."""
#     async with test_engine.begin() as conn:
#         # 1. Enable PostGIS inside the fresh test database space first!
#         await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))

#         await conn.run_sync(Base.metadata.create_all)
#     yield
#     async with test_engine.begin() as conn:
#         await conn.run_sync(Base.metadata.drop_all)


# # ── Function-scoped: each test gets a rolled-back transaction ──────
# @pytest_asyncio.fixture(scope="function")
# async def db_session() -> AsyncGenerator[AsyncSession, None]:
#     """
#     Each test runs in a transaction that gets rolled back after.
#     This means tests don't pollute each other's data.
#     """
#     async with test_engine.begin() as conn:
#         # create a savepoint — we'll roll back to here after each test
#         await conn.begin_nested()

#         session = TestSessionLocal(bind=conn)
#         try:
#             yield session
#         finally:
#             await session.close()
#             await conn.rollback()  # ← undo everything the test did


# # ── Override FastAPI's DB dependency with test DB ──────────────────
# @pytest_asyncio.fixture(scope="function")
# async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
#     """
#     HTTP client that uses the test DB session.
#     Requests go through your real FastAPI app but hit the test DB.
#     """
#     async def override_get_db():
#         yield db_session

#     app.dependency_overrides[get_db_session] = override_get_db

#     async with AsyncClient(
#         transport=ASGITransport(app=app),
#         base_url="http://test",
#     ) as ac:
#         yield ac

#     app.dependency_overrides.clear()


# # ── Reusable test data ─────────────────────────────────────────────
# @pytest.fixture
# def seeker_payload():
#     return {
#         "name_en": "Test Seeker",
#         "name_bn": "টেস্ট সিকার",
#         "phone": "01630956567",
#         "password": "securepassword123",
#     }


# @pytest.fixture
# def provider_payload():
#     return {
#         "name_en": "Test Provider",
#         "name_bn": "টেস্ট প্রোভাইডার",
#         "phone": "01730956568",
#         "password": "securepassword123",
#         "skill_ids": [1, 2, 3],        # empty until skill table has data
#         "latitude": 23.8103,
#         "longitude": 90.4125,
#         "working_radius_km": 2,
#         "has_smartphone": True,
#     }


# # add skills data
# @pytest.fixture
# async def seed_test_skills(db_session):
#     """Inserts mock skills into the isolated test database."""
#     # Ensure a category exists first if your skills table relies on a category foreign key
#     await db_session.execute(
#         text("INSERT INTO categories (id, name_en, name_bn) VALUES (1, 'Test Category', 'টেস্ট ক্যাটাগরি') ON CONFLICT DO NOTHING;")
#     )

#     # Insert mock skills matching your payload ids [1, 2, 3]
#     for skill_id in [1, 2, 3]:
#         await db_session.execute(
#             text(
#                 f"INSERT INTO skills (id, category_id, name_en, name_bn) VALUES ({skill_id}, 1, 'Skill {skill_id}', 'দক্ষতা {skill_id}') ON CONFLICT DO NOTHING;")
#         )

#     await db_session.commit()


# # get access
# @pytest_asyncio.fixture
# async def get_authenticated_provider_token(
#     client: AsyncClient,
#     db_session: AsyncSession,
#     provider_payload: dict,
#     seed_test_skills
# ) -> str:
#     """
#     Registers a fresh provider through the API, then returns access token for protected route testing.
#     Also backdates location and radius update timestamps to allow immediate updates in tests.
#     """
#     PROVIDER_REG_URL = "/api/v1/auth/register/provider"

#     # 1. Register the provider
#     response = await client.post(PROVIDER_REG_URL, json=provider_payload)
#     if response.status_code != 201:
#         pytest.fail(f"Fixture failed to register provider: {response.text}")

#     data = response.json()
#     access_token = data["access_token"]
#     user_id = data["user_id"]

#     # 2. Backdate the update timestamps to bypass the 7-day restriction
#     # Set them to 8 days ago so tests can update immediately
#     past_date = datetime.now(timezone.utc) - timedelta(days=8)

#     await db_session.execute(
#         update(ProviderProfile)
#         .where(ProviderProfile.user_id == user_id)
#         .values(
#             location_updated_at=past_date,
#             radius_updated_at=past_date
#         )
#     )
#     await db_session.commit()

#     return access_token
