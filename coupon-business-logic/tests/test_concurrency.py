"""
Concurrency tests for POST /apply-coupon.

These tests verify the critical invariant:
    For the same (coupon, user), exactly 1 application succeeds,
    regardless of how many concurrent requests are made.

Uses asyncio.Barrier to ensure genuine concurrency — all requests are
held at a synchronization point until every task is ready, then released
simultaneously to contend for the same database state.
"""

import asyncio
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db.database import get_session
from app.db.models import Base
from app.main import app
from tests.conftest import (
    COUPON_ACTIVE_ID,
    USER_1_ID,
    USER_2_ID,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")

CONCURRENT_REQUESTS = 10


async def test_concurrent_same_user_same_coupon(test_session_factory):
    """
    Fire 10 concurrent requests for the SAME user and SAME coupon.

    Expected invariant:
    - Exactly 1 request succeeds (200)
    - Exactly 9 requests are rejected (409)
    - Exactly 1 transaction record in DB
    - Exactly 1 coupon_usage record in DB
    """
    barrier = asyncio.Barrier(CONCURRENT_REQUESTS)

    async def apply_with_barrier(req_client: AsyncClient) -> int:
        await barrier.wait()
        response = await req_client.post(
            "/apply-coupon",
            json={
                "user_id": str(USER_1_ID),
                "coupon_code": "WELCOME100",
                "amount": "100.00",
            },
        )
        return response.status_code

    # Each concurrent task needs its own client to avoid connection sharing.
    # Override the session dependency so each request gets its own DB session.
    async def override_get_session():
        async with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            status_codes = await asyncio.gather(
                *[apply_with_barrier(ac) for _ in range(CONCURRENT_REQUESTS)]
            )
    finally:
        app.dependency_overrides.clear()

    # Exactly 1 success, rest are conflicts
    assert status_codes.count(200) == 1, (
        f"Expected exactly 1 success, got {status_codes.count(200)}. "
        f"Status codes: {status_codes}"
    )
    assert status_codes.count(409) == CONCURRENT_REQUESTS - 1, (
        f"Expected {CONCURRENT_REQUESTS - 1} conflicts, got {status_codes.count(409)}. "
        f"Status codes: {status_codes}"
    )

    # Verify database invariants
    async with test_session_factory() as session:
        result = await session.execute(
            text(
                "SELECT COUNT(*) FROM coupon_usages "
                "WHERE coupon_id = :cid AND user_id = :uid"
            ),
            {"cid": str(COUPON_ACTIVE_ID), "uid": str(USER_1_ID)},
        )
        assert result.scalar() == 1, "Expected exactly 1 coupon_usage record"

        result = await session.execute(
            text(
                "SELECT COUNT(*) FROM transactions "
                "WHERE coupon_id = :cid AND user_id = :uid"
            ),
            {"cid": str(COUPON_ACTIVE_ID), "uid": str(USER_1_ID)},
        )
        assert result.scalar() == 1, "Expected exactly 1 transaction record"


async def test_concurrent_different_users_same_coupon(test_session_factory):
    """
    Fire concurrent requests for DIFFERENT users with the SAME coupon.

    The UNIQUE constraint is on (coupon_id, user_id), so different users
    should independently succeed. This verifies the constraint is
    one-time-per-user, not one-time-globally.
    """
    # Create additional test users for this test
    extra_user_ids = [uuid.uuid4() for _ in range(3)]
    all_user_ids = [USER_1_ID, USER_2_ID] + extra_user_ids

    async with test_session_factory() as session:
        async with session.begin():
            for uid in extra_user_ids:
                await session.execute(
                    text("INSERT INTO users (id) VALUES (:id)"),
                    {"id": str(uid)},
                )

    num_users = len(all_user_ids)
    barrier = asyncio.Barrier(num_users)

    async def apply_for_user(req_client: AsyncClient, user_id: uuid.UUID) -> int:
        await barrier.wait()
        response = await req_client.post(
            "/apply-coupon",
            json={
                "user_id": str(user_id),
                "coupon_code": "WELCOME100",
                "amount": "100.00",
            },
        )
        return response.status_code

    async def override_get_session():
        async with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            status_codes = await asyncio.gather(
                *[apply_for_user(ac, uid) for uid in all_user_ids]
            )
    finally:
        app.dependency_overrides.clear()

    # All users should succeed independently
    assert all(code == 200 for code in status_codes), (
        f"Expected all {num_users} users to succeed. Status codes: {status_codes}"
    )

    # Verify each user has exactly 1 usage and 1 transaction
    async with test_session_factory() as session:
        result = await session.execute(
            text(
                "SELECT COUNT(*) FROM coupon_usages WHERE coupon_id = :cid"
            ),
            {"cid": str(COUPON_ACTIVE_ID)},
        )
        assert result.scalar() == num_users, (
            f"Expected {num_users} coupon_usage records"
        )

        result = await session.execute(
            text(
                "SELECT COUNT(*) FROM transactions WHERE coupon_id = :cid"
            ),
            {"cid": str(COUPON_ACTIVE_ID)},
        )
        assert result.scalar() == num_users, (
            f"Expected {num_users} transaction records"
        )

    # Clean up extra users
    async with test_session_factory() as session:
        async with session.begin():
            for uid in extra_user_ids:
                await session.execute(
                    text("DELETE FROM coupon_usages WHERE user_id = :id"),
                    {"id": str(uid)},
                )
                await session.execute(
                    text("DELETE FROM transactions WHERE user_id = :id"),
                    {"id": str(uid)},
                )
                await session.execute(
                    text("DELETE FROM users WHERE id = :id"),
                    {"id": str(uid)},
                )
