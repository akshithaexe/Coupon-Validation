"""Tests for POST /validate-coupon — read-only coupon validation."""

import pytest
from sqlalchemy import text

from tests.conftest import (
    COUPON_ACTIVE_ID,
    NONEXISTENT_USER_ID,
    USER_1_ID,
    USER_2_ID,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_validate_valid_coupon(client):
    """Valid coupon returns 200 with correct 100% discount calculation."""
    response = await client.post(
        "/validate-coupon",
        json={
            "user_id": str(USER_1_ID),
            "coupon_code": "WELCOME100",
            "amount": "150.00",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["coupon_code"] == "WELCOME100"
    assert data["discount_percentage"] == 100
    assert data["original_amount"] == "150.00"
    assert data["discount_amount"] == "150.00"
    assert data["final_amount"] == "0.00"
    assert data["message"] == "Coupon is valid"


async def test_validate_nonexistent_coupon(client):
    """Nonexistent coupon code returns 404."""
    response = await client.post(
        "/validate-coupon",
        json={
            "user_id": str(USER_1_ID),
            "coupon_code": "DOESNOTEXIST",
            "amount": "100.00",
        },
    )

    assert response.status_code == 404
    data = response.json()["detail"]
    assert data["error"] == "coupon_not_found"


async def test_validate_inactive_coupon(client):
    """Inactive coupon returns 400."""
    response = await client.post(
        "/validate-coupon",
        json={
            "user_id": str(USER_1_ID),
            "coupon_code": "EXPIRED50",
            "amount": "100.00",
        },
    )

    assert response.status_code == 400
    data = response.json()["detail"]
    assert data["error"] == "coupon_inactive"


async def test_validate_already_used_coupon(client, test_session_factory):
    """Coupon already used by this user returns 409."""
    # Pre-create a usage record to simulate prior use
    async with test_session_factory() as session:
        async with session.begin():
            await session.execute(
                text(
                    "INSERT INTO transactions (id, user_id, coupon_id, original_amount, discount_amount, final_amount, status) "
                    "VALUES (gen_random_uuid(), :uid, :cid, 100.00, 100.00, 0.00, 'success')"
                ),
                {"uid": str(USER_1_ID), "cid": str(COUPON_ACTIVE_ID)},
            )
            # Get the transaction id
            result = await session.execute(
                text("SELECT id FROM transactions WHERE user_id = :uid"),
                {"uid": str(USER_1_ID)},
            )
            txn_id = result.scalar_one()
            await session.execute(
                text(
                    "INSERT INTO coupon_usages (id, coupon_id, user_id, transaction_id) "
                    "VALUES (gen_random_uuid(), :cid, :uid, :tid)"
                ),
                {"cid": str(COUPON_ACTIVE_ID), "uid": str(USER_1_ID), "tid": str(txn_id)},
            )

    response = await client.post(
        "/validate-coupon",
        json={
            "user_id": str(USER_1_ID),
            "coupon_code": "WELCOME100",
            "amount": "100.00",
        },
    )

    assert response.status_code == 409
    data = response.json()["detail"]
    assert data["error"] == "coupon_already_used"


async def test_validate_correct_discount_calculation(client):
    """100% discount: discount_amount = amount, final_amount = 0."""
    response = await client.post(
        "/validate-coupon",
        json={
            "user_id": str(USER_1_ID),
            "coupon_code": "WELCOME100",
            "amount": "999.99",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["discount_amount"] == "999.99"
    assert data["final_amount"] == "0.00"


async def test_validate_does_not_modify_database(client, db_session):
    """Validation must be read-only — no transactions or usages created."""
    # Call validate
    response = await client.post(
        "/validate-coupon",
        json={
            "user_id": str(USER_1_ID),
            "coupon_code": "WELCOME100",
            "amount": "100.00",
        },
    )
    assert response.status_code == 200

    # Verify no side effects in the database
    result = await db_session.execute(text("SELECT COUNT(*) FROM transactions"))
    assert result.scalar() == 0

    result = await db_session.execute(text("SELECT COUNT(*) FROM coupon_usages"))
    assert result.scalar() == 0


async def test_validate_user_not_found(client):
    """Nonexistent user returns 404."""
    response = await client.post(
        "/validate-coupon",
        json={
            "user_id": str(NONEXISTENT_USER_ID),
            "coupon_code": "WELCOME100",
            "amount": "100.00",
        },
    )

    assert response.status_code == 404
    data = response.json()["detail"]
    assert data["error"] == "user_not_found"
