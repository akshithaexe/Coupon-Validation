import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="user")
    coupon_usages: Mapped[list["CouponUsage"]] = relationship(back_populates="user")


class Coupon(Base):
    __tablename__ = "coupons"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    discount_percentage: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="coupon")
    coupon_usages: Mapped[list["CouponUsage"]] = relationship(back_populates="coupon")

    __table_args__ = (
        CheckConstraint(
            "discount_percentage > 0 AND discount_percentage <= 100",
            name="ck_coupons_discount_range",
        ),
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    coupon_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("coupons.id"), nullable=False
    )
    original_amount: Mapped[float] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    discount_amount: Mapped[float] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    final_amount: Mapped[float] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="success"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )

    user: Mapped["User"] = relationship(back_populates="transactions")
    coupon: Mapped["Coupon"] = relationship(back_populates="transactions")
    coupon_usage: Mapped["CouponUsage"] = relationship(
        back_populates="transaction", uselist=False
    )

    __table_args__ = (
        CheckConstraint("original_amount > 0", name="ck_transactions_original_positive"),
        CheckConstraint("discount_amount >= 0", name="ck_transactions_discount_nonneg"),
        CheckConstraint("final_amount >= 0", name="ck_transactions_final_nonneg"),
    )


class CouponUsage(Base):
    __tablename__ = "coupon_usages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    coupon_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("coupons.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )

    coupon: Mapped["Coupon"] = relationship(back_populates="coupon_usages")
    user: Mapped["User"] = relationship(back_populates="coupon_usages")
    transaction: Mapped["Transaction"] = relationship(back_populates="coupon_usage")

    # The concurrency correctness constraint: one coupon use per user
    __table_args__ = (
        UniqueConstraint("coupon_id", "user_id", name="uq_coupon_usage_coupon_user"),
    )
