"""Release & Distribution Framework service settings.

Composes ``shared_core.config``'s aggregate settings with the fields
specific to this service: host/port, CORS, JWT verification key, and
every timeout/threshold a background sweep depends on.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from shared_core.config.cache import get_settings as get_shared_settings
from shared_core.config.settings import (
    ApplicationSettings,
    DatabaseSettings,
    EmailSettings,
    MinioSettings,
    RabbitMQSettings,
    RedisSettings,
    TelemetrySettings,
)


class ReleaseDistributionFrameworkSettings(BaseSettings):
    """Fields specific to this service, not covered by any shared_core section."""

    model_config = SettingsConfigDict(
        env_prefix="AIIOS_RELEASE_DISTRIBUTION_FRAMEWORK_", env_file=".env", extra="ignore"
    )

    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8051, ge=1, le=65_535)
    cors_allowed_origins: list[str] = Field(default_factory=list)
    jwt_public_key_path: str = Field(default="keys/jwt_public_key.pem")

    # ---- job thresholds -------------------------------------------------------------------

    build_max_age_hours: int = Field(default=4, ge=1)
    promotion_approval_max_age_hours: int = Field(default=48, ge=1)
    lts_support_expiry_warning_days: int = Field(default=90, ge=1)
    eol_warning_days: int = Field(default=180, ge=1)

    # ---- workers ------------------------------------------------------------------------------

    workers_enabled: bool = Field(default=True)
    build_timeout_sweep_seconds: int = Field(default=300, ge=60, le=86_400)
    promotion_approval_timeout_sweep_seconds: int = Field(default=3600, ge=60, le=86_400)
    lts_support_expiry_sweep_seconds: int = Field(default=3600, ge=60, le=86_400)
    eol_schedule_sweep_seconds: int = Field(default=3600, ge=60, le=86_400)
    statistics_rollup_seconds: int = Field(default=900, ge=60, le=86_400)


@dataclass(frozen=True, slots=True)
class Settings:
    """Every configuration section this service actually uses."""

    application: ApplicationSettings
    database: DatabaseSettings
    redis: RedisSettings
    rabbitmq: RabbitMQSettings
    email: EmailSettings
    minio: MinioSettings
    telemetry: TelemetrySettings
    service: ReleaseDistributionFrameworkSettings


def build_settings() -> Settings:
    """Assemble this service's settings from the shared sections plus its own."""
    shared = get_shared_settings()
    return Settings(
        application=shared.application,
        database=shared.database,
        redis=shared.redis,
        rabbitmq=shared.rabbitmq,
        email=shared.email,
        minio=shared.minio,
        telemetry=shared.telemetry,
        service=ReleaseDistributionFrameworkSettings(),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """The process-wide settings.

    Cached, so a test that changes the environment must call
    ``get_settings.cache_clear()`` both before *and* after -- before to
    pick its change up, after so it does not leak into the next test.
    """
    return build_settings()


__all__ = ["ReleaseDistributionFrameworkSettings", "Settings", "build_settings", "get_settings"]
