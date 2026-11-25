from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CodeAtlas API"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://codeatlas:codeatlas@localhost:5432/codeatlas"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "change-this-secret-before-deployment"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 1440
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    max_archive_bytes: int = 30 * 1024 * 1024
    max_repository_files: int = 2500
    max_source_file_bytes: int = 1_000_000
    max_repository_bytes: int = 100 * 1024 * 1024
    analysis_job_timeout_seconds: int = 3600
    analysis_stale_job_seconds: int = 300
    analysis_recovery_interval_seconds: int = 60

    model_config = SettingsConfigDict(env_file=("../.env", ".env"), env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def require_production_secret(self):
        if self.environment.lower() in {"production", "prod"} and (self.jwt_secret == "change-this-secret-before-deployment" or "replace-with" in self.jwt_secret or len(self.jwt_secret) < 32):
            raise ValueError("Set JWT_SECRET to a private random value in production")
        return self

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
