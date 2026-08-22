from fastapi import FastAPI

from app.api.routes.coupons import router as coupon_router

app = FastAPI(
    title="Coupon Business Logic API",
    description="One-time-per-user, 100% discount coupon system with concurrency-safe application.",
    version="1.0.0",
)

app.include_router(coupon_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
