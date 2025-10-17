"""Application configuration management."""

from __future__ import annotations

from functools import lru_cache
from typing import List, Literal

from pydantic import BaseSettings, Field, validator

import json


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    database_url: str | None = Field(default=None, env="DATABASE_URL")
    api_auth_enabled: bool = Field(default=True)
    api_key_header: str = Field(default="X-API-Key")
    rate_limit_per_minute: int = Field(default=180, ge=1)
    rate_limit_burst: int = Field(default=60, ge=0)
    rate_limit_enabled: bool = Field(default=True)
    rate_limit_identifier_header: str = Field(default="X-API-Key")
    rate_limit_backend: str = Field(default="memory")
    rate_limit_redis_url: str | None = Field(default=None)
    allowed_origins: List[str] = Field(default_factory=lambda: ["*"])
    api_hmac_enabled: bool = Field(default=False)
    api_signature_header: str = Field(default="X-Signature")
    api_timestamp_header: str = Field(default="X-Timestamp")
    api_timestamp_tolerance_seconds: int = Field(default=300, ge=1)
    metrics_key: str | None = Field(default=None)
    metrics_key_header: str = Field(default="X-Metrics-Key")
    metrics_cache_seconds: int = Field(default=15, ge=0)
    metrics_cache_overrides: dict[str, int] = Field(default_factory=dict)
    metrics_cache_bypass_query: str = Field(default="refresh")
    api_key_default_ttl_days: int = Field(default=0, ge=0)
    api_key_expiry_check_seconds: int = Field(default=900, ge=60)
    api_key_auto_expiry_enabled: bool = Field(default=True)
    vault_enabled: bool = Field(default=False)
    vault_addr: str | None = Field(default=None)
    vault_token: str | None = Field(default=None)
    vault_namespace: str | None = Field(default=None)
    vault_mount_point: str = Field(default="secret")
    vault_path_prefix: str = Field(default="task-registry/api-keys")
    vault_verify_ssl: bool = Field(default=True)
    vault_verify_writes: bool = Field(default=False)
    vault_transit_key: str | None = Field(default=None)
    vault_transit_key_version: int | None = Field(default=None, ge=1)
    audit_log_enabled: bool = Field(default=True)
    audit_log_destination: Literal["stdout", "file", "http"] = Field(default="stdout")
    audit_log_file_path: str | None = Field(default=None)
    audit_log_http_endpoint: str | None = Field(default=None)
    audit_queue_enabled: bool = Field(default=False)
    audit_queue_backend: Literal["memory", "kafka"] = Field(default="memory")
    audit_queue_kafka_bootstrap: str | None = Field(default=None)
    audit_queue_kafka_topic: str | None = Field(default=None)
    audit_queue_memory_maxsize: int = Field(default=10000, ge=0)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @validator("metrics_cache_overrides", pre=True)
    def _parse_metrics_overrides(cls, value):  # noqa: D401, ANN001
        if not value:
            return {}
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError as exc:  # pragma: no cover - defensive
                raise ValueError("METRICS_CACHE_OVERRIDES must be valid JSON") from exc
            if not isinstance(parsed, dict):
                raise ValueError("METRICS_CACHE_OVERRIDES must decode to a dictionary")
            return parsed
        raise ValueError("Unsupported type for METRICS_CACHE_OVERRIDES")


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings()


def reset_settings_cache() -> None:
    """Clear cached settings (useful for tests)."""

    get_settings.cache_clear()
