from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class CouponRequest(BaseModel):
    """Shared request body for both /validate-coupon and /apply-coupon."""

    user_id: UUID
    coupon_code: str = Field(..., min_length=1, max_length=50)
    amount: Decimal = Field(..., gt=0, max_digits=12, decimal_places=2)


class ValidateCouponResponse(BaseModel):
    valid: bool
    coupon_code: str
    discount_percentage: int
    original_amount: Decimal
    discount_amount: Decimal
    final_amount: Decimal
    message: str


class ApplyCouponResponse(BaseModel):
    transaction_id: UUID
    user_id: UUID
    coupon_code: str
    original_amount: Decimal
    discount_amount: Decimal
    final_amount: Decimal
    status: str
    applied_at: datetime
    message: str


class ErrorResponse(BaseModel):
    error: str
    message: str
