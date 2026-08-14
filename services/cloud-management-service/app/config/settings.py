"""Cloud management service settings.

Composes ``shared_core.config``'s aggregate settings with the fields
specific to this service: host/port, CORS, JWT verification key,
discovery/provisioning/FinOps/compliance thresholds.

**Every threshold a cloud-fleet decision depends on is configuration,
not a constant.** A discovery interval, a budget warning threshold, or a
drift staleness window compiled into the code is one a deployment
cannot tune to its own account portfolio's real size and spend pattern
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


class CloudManagementServiceSettings(BaseSettings):
    """Fields specific to this service, not covered by any shared_core section."""

    model_config = SettingsConfigDict(
        env_prefix="AIIOS_CLOUD_MANAGEMENT_SERVICE_", env_file=".env", extra="ignore"
    )

    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8039, ge=1, le=65_535)
    cors_allowed_origins: list[str] = Field(default_factory=list)
    jwt_public_key_path: str = Field(default="keys/jwt_public_key.pem")

    # ---- accounts / discovery -----------------------------------------------------------

    stale_account_threshold_minutes: int = Field(default=1_440, ge=1)
    """An account whose ``last_validated_at`` is older than this is
    reported ``UNHEALTHY`` by the account health worker."""
    stale_resource_threshold_minutes: int = Field(default=1_440, ge=1)
    """A resource whose ``last_synced_at`` is older than this is treated
    as due for rediscovery / drift reclassification."""

    # ---- FinOps ---------------------------------------------------------------------------

    budget_warning_utilization_fraction: float = Field(default=0.8, ge=0.0, le=1.0)
    budget_critical_utilization_fraction: float = Field(default=1.0, ge=0.0, le=1.0)
    idle_resource_threshold_days: int = Field(default=14, ge=1)

    # ---- compliance -----------------------------------------------------------------------

    compliance_reassessment_days: int = Field(default=30, ge=1)
    compliance_remediation_grace_days: int = Field(default=14, ge=1)

    # ---- drift ------------------------------------------------------------------------------

    drift_sweep_stale_after_minutes: int = Field(default=1_440, ge=1)

    # ---- workers ------------------------------------------------------------------------------

    workers_enabled: bool = Field(default=True)
    account_health_sweep_seconds: int = Field(default=300, ge=30, le=86_400)
    drift_sweep_seconds: int = Field(default=900, ge=60, le=86_400)
    budget_sweep_seconds: int = Field(default=900, ge=60, le=86_400)
    compliance_sweep_seconds: int = Field(default=3_600, ge=60, le=604_800)
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
    service: CloudManagementServiceSettings


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
        service=CloudManagementServiceSettings(),
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
    "CloudManagementServiceSettings",
    "Settings",
    "build_settings",
    "get_settings",
]
