from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5433/coupon_db"
    SYNC_DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@127.0.0.1:5433/coupon_db"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
