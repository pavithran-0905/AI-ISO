"""Mobile API service settings.

Composes ``shared_core.config``'s aggregate settings with the fields
specific to this service: host/port, CORS, JWT verification key, and
every session/token/sync/push threshold a background sweep depends on.

**Every threshold a device or session decision depends on is
configuration, not a constant.** A session lifetime or a sync retry
policy compiled into the code is one a deployment cannot tune to its
own mobile release cadence without shipping a new build of this
service itself.
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


class MobileApiServiceSettings(BaseSettings):
    """Fields specific to this service, not covered by any shared_core section."""

    model_config = SettingsConfigDict(
        env_prefix="AIIOS_MOBILE_API_SERVICE_", env_file=".env", extra="ignore"
    )

    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8043, ge=1, le=65_535)
    cors_allowed_origins: list[str] = Field(default_factory=list)
    jwt_public_key_path: str = Field(default="keys/jwt_public_key.pem")

    # ---- sessions / tokens --------------------------------------------------------------

    session_max_age_minutes: int = Field(default=720, ge=1)
    session_expiry_warning_minutes: int = Field(default=30, ge=1)
    token_max_age_days: int = Field(default=90, ge=1)

    # ---- sync / offline -----------------------------------------------------------------

    sync_max_retry_count: int = Field(default=5, ge=1, le=50)
    sync_retry_backoff_base_seconds: int = Field(default=30, ge=1)

    # ---- push notifications --------------------------------------------------------------

    push_max_retry_count: int = Field(default=5, ge=1, le=50)

    # ---- QR / onboarding ------------------------------------------------------------------

    qr_token_ttl_minutes: int = Field(default=15, ge=1)

    # ---- workers ------------------------------------------------------------------------------

    workers_enabled: bool = Field(default=True)
    session_expiry_sweep_seconds: int = Field(default=300, ge=60, le=86_400)
    token_expiry_sweep_seconds: int = Field(default=3_600, ge=60, le=604_800)
    sync_queue_retry_sweep_seconds: int = Field(default=60, ge=15, le=86_400)
    push_delivery_retry_sweep_seconds: int = Field(default=60, ge=15, le=86_400)
    app_version_compliance_sweep_seconds: int = Field(default=3_600, ge=60, le=604_800)


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
    service: MobileApiServiceSettings


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
        service=MobileApiServiceSettings(),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """The process-wide settings.

    Cached, so a test that changes the environment must call
    ``get_settings.cache_clear()`` both before *and* after -- before to
    pick its change up, after so it does not leak into the next test.
    """
    return build_settings()


__all__ = ["MobileApiServiceSettings", "Settings", "build_settings", "get_settings"]
