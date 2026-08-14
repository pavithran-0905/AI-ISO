"""Multi-cluster management service settings.

Composes ``shared_core.config``'s aggregate settings with the fields
specific to this service: host/port, CORS, JWT verification key, fleet
registration/validation, health monitoring, capacity, upgrade, policy
propagation, compliance, and GitOps defaults.

**Every threshold a fleet decision depends on is configuration, not a
constant.** A health-check interval, a capacity warning threshold, or an
upgrade version-skew limit compiled into the code is one a deployment
cannot adjust to its own fleet's real operating characteristics without
a release.
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


class MultiClusterManagementServiceSettings(BaseSettings):
    """Fields specific to this service, not covered by any shared_core section."""

    model_config = SettingsConfigDict(
        env_prefix="AIIOS_MULTI_CLUSTER_MANAGEMENT_SERVICE_", env_file=".env", extra="ignore"
    )

    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8037, ge=1, le=65_535)
    cors_allowed_origins: list[str] = Field(default_factory=list)
    jwt_public_key_path: str = Field(default="keys/jwt_public_key.pem")

    # ---- registration / validation --------------------------------------------------------

    credential_validation_timeout_seconds: float = Field(default=30.0, gt=0)
    stale_cluster_threshold_minutes: int = Field(default=15, ge=1)
    """A cluster whose ``last_seen_at`` is older than this is reported
    ``OFFLINE`` by the health worker rather than whatever status it last
    reported -- a cluster that stopped phoning home is not still
    healthy just because nothing has since said otherwise."""

    # ---- health monitoring ------------------------------------------------------------------

    health_check_interval_seconds: int = Field(default=60, ge=10)
    health_degraded_component_threshold: int = Field(default=1, ge=1)
    health_unhealthy_component_threshold: int = Field(default=2, ge=1)

    # ---- capacity ---------------------------------------------------------------------------

    capacity_warning_utilization_fraction: float = Field(default=0.80, gt=0.0, le=1.0)
    capacity_critical_utilization_fraction: float = Field(default=0.92, gt=0.0, le=1.0)

    # ---- upgrades ---------------------------------------------------------------------------

    max_supported_version_skew: int = Field(default=2, ge=0)
    """The maximum number of catalog version steps a cluster may upgrade
    across in one operation, mirroring upstream Kubernetes' own
    single-minor-version skew policy generalised across distributions."""
    upgrade_default_strategy: str = Field(default="rolling")

    # ---- policy propagation -----------------------------------------------------------------

    policy_propagation_timeout_seconds: float = Field(default=60.0, gt=0)
    policy_drift_check_interval_seconds: int = Field(default=1_800, ge=60)

    # ---- compliance -------------------------------------------------------------------------

    compliance_reassessment_days: int = Field(default=30, ge=1)
    compliance_remediation_grace_days: int = Field(default=14, ge=0)

    # ---- gitops -----------------------------------------------------------------------------

    gitops_sync_check_interval_seconds: int = Field(default=300, ge=30)

    # ---- workers ----------------------------------------------------------------------------

    workers_enabled: bool = Field(default=True)
    health_sweep_seconds: int = Field(default=60, ge=10, le=3_600)
    capacity_sweep_seconds: int = Field(default=300, ge=30, le=86_400)
    compliance_sweep_seconds: int = Field(default=3_600, ge=60, le=604_800)
    policy_drift_sweep_seconds: int = Field(default=1_800, ge=60, le=604_800)
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
    service: MultiClusterManagementServiceSettings


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
        service=MultiClusterManagementServiceSettings(),
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
    "MultiClusterManagementServiceSettings",
    "Settings",
    "build_settings",
    "get_settings",
]
