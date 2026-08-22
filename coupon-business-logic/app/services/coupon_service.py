from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Coupon, CouponUsage, Transaction, User
from app.schemas.coupon import (
    ApplyCouponResponse,
    CouponRequest,
    ValidateCouponResponse,
)


async def _get_user_or_404(session: AsyncSession, user_id: UUID) -> User:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "user_not_found", "message": "User not found"},
        )
    return user


async def _get_coupon_or_404(session: AsyncSession, coupon_code: str) -> Coupon:
    result = await session.execute(
        select(Coupon).where(Coupon.code == coupon_code)
    )
    coupon = result.scalar_one_or_none()
    if coupon is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "coupon_not_found", "message": "Coupon not found"},
        )
    return coupon


async def _check_coupon_active(coupon: Coupon) -> None:
    if not coupon.is_active:
        raise HTTPException(
            status_code=400,
            detail={"error": "coupon_inactive", "message": "Coupon is inactive"},
        )


async def _check_not_already_used(
    session: AsyncSession, coupon_id: UUID, user_id: UUID
) -> None:
    result = await session.execute(
        select(CouponUsage).where(
            CouponUsage.coupon_id == coupon_id,
            CouponUsage.user_id == user_id,
        )
    )
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "coupon_already_used",
                "message": "This coupon has already been used by this user",
            },
        )


def _calculate_discount(
    amount: Decimal, discount_percentage: int
) -> tuple[Decimal, Decimal]:
    """Returns (discount_amount, final_amount)."""
    discount_amount = amount * Decimal(discount_percentage) / Decimal(100)
    final_amount = amount - discount_amount
    return discount_amount, final_amount


async def validate_coupon(
    session: AsyncSession, request: CouponRequest
) -> ValidateCouponResponse:
    """
    Validate a coupon without modifying any database state.
    This is a read-only operation.
    """
    await _get_user_or_404(session, request.user_id)
    coupon = await _get_coupon_or_404(session, request.coupon_code)
    await _check_coupon_active(coupon)
    await _check_not_already_used(session, coupon.id, request.user_id)

    discount_amount, final_amount = _calculate_discount(
        request.amount, coupon.discount_percentage
    )

    return ValidateCouponResponse(
        valid=True,
        coupon_code=coupon.code,
        discount_percentage=coupon.discount_percentage,
        original_amount=request.amount,
        discount_amount=discount_amount,
        final_amount=final_amount,
        message="Coupon is valid",
    )


async def apply_coupon(
    session: AsyncSession, request: CouponRequest
) -> ApplyCouponResponse:
    """
    Apply a coupon atomically: validate, create transaction, record usage.

    Concurrency strategy:
    - All operations happen inside a single database transaction.
    - The UNIQUE(coupon_id, user_id) constraint on coupon_usages is the
      source of truth for concurrency correctness.
    - If two concurrent requests both pass the app-level usage check,
      only one INSERT INTO coupon_usages will succeed. The other will
      raise IntegrityError, which triggers an automatic rollback of the
      entire transaction (including the transaction record).
    """
    try:
        async with session.begin():
            # Step 1: Validate user exists
            await _get_user_or_404(session, request.user_id)

            # Step 2: Validate coupon exists and is active
            coupon = await _get_coupon_or_404(session, request.coupon_code)
            await _check_coupon_active(coupon)

            # Step 3: App-level check — catches the common (non-concurrent) case
            await _check_not_already_used(session, coupon.id, request.user_id)

            # Step 4: Calculate discount
            discount_amount, final_amount = _calculate_discount(
                request.amount, coupon.discount_percentage
            )

            # Step 5: Create transaction record
            transaction = Transaction(
                user_id=request.user_id,
                coupon_id=coupon.id,
                original_amount=request.amount,
                discount_amount=discount_amount,
                final_amount=final_amount,
                status="success",
            )
            session.add(transaction)

            # Flush to get the transaction ID for the coupon_usage FK
            await session.flush()

            # Step 6: Record coupon usage
            # This INSERT triggers the UNIQUE constraint if a concurrent
            # request already committed a usage for the same (coupon, user).
            usage = CouponUsage(
                coupon_id=coupon.id,
                user_id=request.user_id,
                transaction_id=transaction.id,
            )
            session.add(usage)

            # Flush to trigger any constraint violations before commit
            await session.flush()

        # If we reach here, COMMIT succeeded
        return ApplyCouponResponse(
            transaction_id=transaction.id,
            user_id=request.user_id,
            coupon_code=coupon.code,
            original_amount=request.amount,
            discount_amount=discount_amount,
            final_amount=final_amount,
            status=transaction.status,
            applied_at=transaction.created_at,
            message="Coupon applied successfully",
        )

    except IntegrityError:
        # The UNIQUE constraint on (coupon_id, user_id) was violated.
        # session.begin() context manager has already rolled back the
        # transaction, so no manual rollback is needed.
        # Both the transaction record and the coupon usage are gone.
        raise HTTPException(
            status_code=409,
            detail={
                "error": "coupon_already_used",
                "message": "This coupon has already been used by this user",
            },
        )
