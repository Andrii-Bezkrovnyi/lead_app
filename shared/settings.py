from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    service_name: str = Field(default="lead-system")
    environment: str = Field(default="local")

    jwt_secret_key: str = Field(default="change-me-super-long-secret-change-me")
    jwt_algorithm: str = Field(default="HS256")
    jwt_issuer: str = Field(default="lead-system")
    jwt_audience: str = Field(default="lead-api")

    access_token_ttl_seconds: int = Field(default=15 * 60)
    refresh_token_ttl_seconds: int = Field(default=7 * 24 * 60 * 60)

    redis_url: str = Field(default="redis://redis:6379/0")
    database_url: str = Field(default="postgresql+asyncpg://postgres:postgres@db:5432/leads")

    rate_limit_requests: int = Field(default=60)
    rate_limit_window_seconds: int = Field(default=60)

    leads_stream_name: str = Field(default="stream:leads")
    leads_dlq_stream_name: str = Field(default="stream:leads:dlq")
    leads_consumer_group: str = Field(default="core-workers")
    leads_consumer_name: str = Field(default="core-worker-1")
    leads_claim_idle_ms: int = Field(default=30_000)
    leads_max_retries: int = Field(default=3)
    retry_key_ttl_seconds: int = Field(default=24 * 60 * 60)

    otel_service_name: str = Field(default="lead-system")
    otel_exporter_otlp_endpoint: str = Field(default="")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(default="INFO")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
