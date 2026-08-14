"""Edge management service settings.

Composes ``shared_core.config``'s aggregate settings with the fields
specific to this service: host/port, CORS, JWT verification key,
provisioning/health/sync/OTA/AI-model/protocol thresholds.

**Every threshold an edge fleet decision depends on is configuration,
not a constant.** A staleness window, an update rollout batch size, or a
sync retry backoff compiled into the code is one a deployment cannot
tune to its own fleet's real bandwidth and reliability characteristics
without a release.
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


class EdgeManagementServiceSettings(BaseSettings):
    """Fields specific to this service, not covered by any shared_core section."""

    model_config = SettingsConfigDict(
        env_prefix="AIIOS_EDGE_MANAGEMENT_SERVICE_", env_file=".env", extra="ignore"
    )

    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8038, ge=1, le=65_535)
    cors_allowed_origins: list[str] = Field(default_factory=list)
    jwt_public_key_path: str = Field(default="keys/jwt_public_key.pem")

    # ---- provisioning / health -----------------------------------------------------------

    stale_device_threshold_minutes: int = Field(default=15, ge=1)
    """A device whose ``last_seen_at`` is older than this is reported
    ``OFFLINE`` by the health worker rather than whatever status it last
    reported."""
    health_degraded_component_threshold: int = Field(default=1, ge=1)
    health_unhealthy_component_threshold: int = Field(default=2, ge=1)

    # ---- synchronization --------------------------------------------------------------------

    sync_retry_max_attempts: int = Field(default=5, ge=1)
    sync_stale_threshold_minutes: int = Field(default=60, ge=1)
    """A device that has never completed a sync within this window is
    flagged by the synchronization sweep as overdue."""

    # ---- OTA / firmware ----------------------------------------------------------------------

    max_supported_firmware_skew: int = Field(default=2, ge=0)
    update_default_strategy: str = Field(default="staged")

    # ---- edge AI ------------------------------------------------------------------------------

    ai_model_health_check_interval_seconds: int = Field(default=300, ge=30)

    # ---- workers ------------------------------------------------------------------------------

    workers_enabled: bool = Field(default=True)
    health_sweep_seconds: int = Field(default=60, ge=10, le=3_600)
    synchronization_sweep_seconds: int = Field(default=300, ge=30, le=86_400)
    update_reconcile_seconds: int = Field(default=1_800, ge=60, le=604_800)
    protocol_sweep_seconds: int = Field(default=300, ge=30, le=86_400)
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
    service: EdgeManagementServiceSettings


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
        service=EdgeManagementServiceSettings(),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """The process-wide settings.

    Cached, so a test that changes the environment must call
    ``get_settings.cache_clear()`` both before *and* after -- before to
    pick its change up, after so it does not leak into the next test.
    """
    return build_settings()


__all__ = [
    "EdgeManagementServiceSettings",
    "Settings",
    "build_settings",
    "get_settings",
]
