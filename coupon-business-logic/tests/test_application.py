"""Tests for POST /apply-coupon — atomic coupon application."""

import pytest
from sqlalchemy import text

from tests.conftest import (
    COUPON_ACTIVE_ID,
    NONEXISTENT_USER_ID,
    USER_1_ID,
    USER_2_ID,
)

pytestmark = pytest.mark.asyncio


async def test_apply_coupon_success(client):
    """Successful coupon application returns 200 with transaction details."""
    response = await client.post(
        "/apply-coupon",
        json={
            "user_id": str(USER_1_ID),
            "coupon_code": "WELCOME100",
            "amount": "150.00",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == str(USER_1_ID)
    assert data["coupon_code"] == "WELCOME100"
    assert data["original_amount"] == "150.00"
    assert data["discount_amount"] == "150.00"
    assert data["final_amount"] == "0.00"
    assert data["status"] == "success"
    assert data["transaction_id"] is not None
    assert data["applied_at"] is not None
    assert data["message"] == "Coupon applied successfully"


async def test_apply_creates_transaction_record(client, db_session):
    """After successful application, a transaction record exists in the DB."""
    await client.post(
        "/apply-coupon",
        json={
            "user_id": str(USER_1_ID),
            "coupon_code": "WELCOME100",
            "amount": "200.00",
        },
    )

    result = await db_session.execute(
        text("SELECT * FROM transactions WHERE user_id = :uid AND coupon_id = :cid"),
        {"uid": str(USER_1_ID), "cid": str(COUPON_ACTIVE_ID)},
    )
    row = result.mappings().one()
    assert float(row["original_amount"]) == 200.00
    assert float(row["discount_amount"]) == 200.00
    assert float(row["final_amount"]) == 0.00
    assert row["status"] == "success"


async def test_apply_creates_coupon_usage_record(client, db_session):
    """After successful application, a coupon_usage record exists in the DB."""
    await client.post(
        "/apply-coupon",
        json={
            "user_id": str(USER_1_ID),
            "coupon_code": "WELCOME100",
            "amount": "100.00",
        },
    )

    result = await db_session.execute(
        text("SELECT * FROM coupon_usages WHERE user_id = :uid AND coupon_id = :cid"),
        {"uid": str(USER_1_ID), "cid": str(COUPON_ACTIVE_ID)},
    )
    row = result.mappings().one()
    assert row["transaction_id"] is not None


async def test_apply_nonexistent_coupon(client):
    """Applying a nonexistent coupon returns 404."""
    response = await client.post(
        "/apply-coupon",
        json={
            "user_id": str(USER_1_ID),
            "coupon_code": "DOESNOTEXIST",
            "amount": "100.00",
        },
    )

    assert response.status_code == 404
    data = response.json()["detail"]
    assert data["error"] == "coupon_not_found"


async def test_apply_inactive_coupon(client):
    """Applying an inactive coupon returns 400."""
    response = await client.post(
        "/apply-coupon",
        json={
            "user_id": str(USER_1_ID),
            "coupon_code": "EXPIRED50",
            "amount": "100.00",
        },
    )

    assert response.status_code == 400
    data = response.json()["detail"]
    assert data["error"] == "coupon_inactive"


async def test_apply_already_used_coupon(client):
    """Second application by same user returns 409."""
    # First application — should succeed
    response1 = await client.post(
        "/apply-coupon",
        json={
            "user_id": str(USER_1_ID),
            "coupon_code": "WELCOME100",
            "amount": "100.00",
        },
    )
    assert response1.status_code == 200

    # Second application — should fail
    response2 = await client.post(
        "/apply-coupon",
        json={
            "user_id": str(USER_1_ID),
            "coupon_code": "WELCOME100",
            "amount": "100.00",
        },
    )
    assert response2.status_code == 409
    data = response2.json()["detail"]
    assert data["error"] == "coupon_already_used"


async def test_apply_user_not_found(client):
    """Applying with nonexistent user returns 404."""
    response = await client.post(
        "/apply-coupon",
        json={
            "user_id": str(NONEXISTENT_USER_ID),
            "coupon_code": "WELCOME100",
            "amount": "100.00",
        },
    )

    assert response.status_code == 404
    data = response.json()["detail"]
    assert data["error"] == "user_not_found"


async def test_failed_apply_no_transaction_or_usage(client, db_session):
    """Failed application must not leave any transaction or usage records."""
    # Apply with nonexistent coupon (will fail)
    response = await client.post(
        "/apply-coupon",
        json={
            "user_id": str(USER_1_ID),
            "coupon_code": "DOESNOTEXIST",
            "amount": "100.00",
        },
    )
    assert response.status_code == 404

    # Verify no records were created
    result = await db_session.execute(
        text("SELECT COUNT(*) FROM transactions WHERE user_id = :uid"),
        {"uid": str(USER_1_ID)},
    )
    assert result.scalar() == 0

    result = await db_session.execute(
        text("SELECT COUNT(*) FROM coupon_usages WHERE user_id = :uid"),
        {"uid": str(USER_1_ID)},
    )
    assert result.scalar() == 0


async def test_failed_apply_coupon_still_usable(client):
    """After a failed application, the coupon should still be usable by another user."""
    # Fail: apply with inactive coupon
    response = await client.post(
        "/apply-coupon",
        json={
            "user_id": str(USER_1_ID),
            "coupon_code": "EXPIRED50",
            "amount": "100.00",
        },
    )
    assert response.status_code == 400

    # The active coupon should still be usable
    response = await client.post(
        "/apply-coupon",
        json={
            "user_id": str(USER_1_ID),
            "coupon_code": "WELCOME100",
            "amount": "100.00",
        },
    )
    assert response.status_code == 200


async def test_different_users_can_use_same_coupon(client):
    """Two different users can each use the same coupon once."""
    response1 = await client.post(
        "/apply-coupon",
        json={
            "user_id": str(USER_1_ID),
            "coupon_code": "WELCOME100",
            "amount": "100.00",
        },
    )
    assert response1.status_code == 200

    response2 = await client.post(
        "/apply-coupon",
        json={
            "user_id": str(USER_2_ID),
            "coupon_code": "WELCOME100",
            "amount": "200.00",
        },
    )
    assert response2.status_code == 200
