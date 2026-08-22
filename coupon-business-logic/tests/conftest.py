import asyncio
import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.database import get_session
from app.db.models import Base
from app.main import app

# ---------------------------------------------------------------------------
# Test database setup
# ---------------------------------------------------------------------------
# Use the same database URL but with a _test suffix to avoid polluting dev data.
# The test database is created/dropped per test session.

TEST_DB_NAME = "coupon_db_test"

# Build a URL pointing at the default 'postgres' database for admin operations
_base_url = settings.DATABASE_URL.rsplit("/", 1)[0]
ADMIN_DB_URL = f"{_base_url}/postgres"
TEST_DB_URL = f"{_base_url}/{TEST_DB_NAME}"


@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create the test database, yield an engine, then drop the test database."""
    # Connect to the default 'postgres' database to create/drop the test DB
    admin_engine = create_async_engine(ADMIN_DB_URL, isolation_level="AUTOCOMMIT")

    async with admin_engine.connect() as conn:
        # Drop if leftover from a previous failed run
        await conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}"))
        await conn.execute(text(f"CREATE DATABASE {TEST_DB_NAME}"))

    await admin_engine.dispose()

    # Create the engine for the test database
    engine = create_async_engine(TEST_DB_URL, echo=False)

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Teardown: drop all tables and the test database
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()

    admin_engine = create_async_engine(ADMIN_DB_URL, isolation_level="AUTOCOMMIT")
    async with admin_engine.connect() as conn:
        await conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}"))
    await admin_engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def test_session_factory(test_engine):
    """Yield an async session factory bound to the test database."""
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    yield factory


@pytest_asyncio.fixture
async def db_session(test_session_factory) -> AsyncGenerator[AsyncSession, None]:
    """Yield a session for direct DB queries in tests, with rollback after each test."""
    async with test_session_factory() as session:
        yield session
        # Rollback any uncommitted changes after each test
        await session.rollback()


@pytest_asyncio.fixture
async def client(test_session_factory) -> AsyncGenerator[AsyncClient, None]:
    """
    Yield an httpx AsyncClient wired to the FastAPI app with the test database.

    Each request gets its own session from the test session factory.
    """

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Seed data constants (matching the Alembic seed migration)
# ---------------------------------------------------------------------------
USER_1_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
USER_2_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
COUPON_ACTIVE_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
COUPON_INACTIVE_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
NONEXISTENT_USER_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")


@pytest_asyncio.fixture(autouse=True)
async def seed_and_cleanup(test_session_factory):
    """
    Insert deterministic seed data before each test and clean up after.

    This ensures each test starts with a known database state:
    - 2 users
    - 1 active coupon (WELCOME100, 100%)
    - 1 inactive coupon (EXPIRED50, 50%)
    - No transactions or coupon_usages
    """
    async with test_session_factory() as session:
        async with session.begin():
            await session.execute(
                text("INSERT INTO users (id) VALUES (:id1), (:id2) ON CONFLICT DO NOTHING"),
                {"id1": str(USER_1_ID), "id2": str(USER_2_ID)},
            )
            await session.execute(
                text(
                    "INSERT INTO coupons (id, code, discount_percentage, is_active) "
                    "VALUES (:id1, :code1, :pct1, :active1), (:id2, :code2, :pct2, :active2) "
                    "ON CONFLICT DO NOTHING"
                ),
                {
                    "id1": str(COUPON_ACTIVE_ID),
                    "code1": "WELCOME100",
                    "pct1": 100,
                    "active1": True,
                    "id2": str(COUPON_INACTIVE_ID),
                    "code2": "EXPIRED50",
                    "pct2": 50,
                    "active2": False,
                },
            )

    yield

    # Clean up after each test: remove usage/transaction data, keep users/coupons
    async with test_session_factory() as session:
        async with session.begin():
            await session.execute(text("DELETE FROM coupon_usages"))
            await session.execute(text("DELETE FROM transactions"))
