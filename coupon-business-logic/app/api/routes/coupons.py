from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.schemas.coupon import (
    ApplyCouponResponse,
    CouponRequest,
    ErrorResponse,
    ValidateCouponResponse,
)
from app.services import coupon_service

router = APIRouter()


@router.post(
    "/validate-coupon",
    response_model=ValidateCouponResponse,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
async def validate_coupon(
    request: CouponRequest,
    session: AsyncSession = Depends(get_session),
) -> ValidateCouponResponse:
    """Validate a coupon without modifying state. Read-only."""
    return await coupon_service.validate_coupon(session, request)


@router.post(
    "/apply-coupon",
    response_model=ApplyCouponResponse,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
async def apply_coupon(
    request: CouponRequest,
    session: AsyncSession = Depends(get_session),
) -> ApplyCouponResponse:
    """Apply a coupon atomically. Creates transaction and records usage."""
    return await coupon_service.apply_coupon(session, request)
