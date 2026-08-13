"""Backup & disaster recovery service settings.

Composes ``shared_core.config``'s aggregate settings with the fields
specific to this service: host/port, CORS, JWT verification key, backup
scheduling and retention defaults, replication and failover thresholds,
and encryption/immutability policy.

**Every threshold a recovery decision depends on is configuration, not a
constant.** An RPO/RTO target, a bandwidth cap, or a retention lock
duration compiled into the code is one a deployment cannot adjust
without a release -- and a disaster recovery service that cannot be
tuned to the business's actual continuity requirements is decorative.
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


class BackupDrServiceSettings(BaseSettings):
    """Fields specific to this service, not covered by any shared_core section."""

    model_config = SettingsConfigDict(
        env_prefix="AIIOS_BACKUP_DR_SERVICE_", env_file=".env", extra="ignore"
    )

    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8036, ge=1, le=65_535)
    cors_allowed_origins: list[str] = Field(default_factory=list)
    jwt_public_key_path: str = Field(default="keys/jwt_public_key.pem")

    # ---- backup -----------------------------------------------------------------

    default_full_interval_days: int = Field(default=7, ge=1)
    default_incremental_interval_hours: int = Field(default=6, ge=1)
    max_concurrent_backup_jobs: int = Field(default=5, ge=1)
    backup_job_timeout_seconds: int = Field(default=14_400, ge=60)
    """Four hours. A backup job with no timeout can wedge a worker slot
    forever on a target that stopped responding mid-transfer, silently
    starving every other job behind it."""
    checksum_algorithm: str = Field(default="sha256")

    # ---- snapshots ----------------------------------------------------------------

    snapshot_default_expiry_days: int = Field(default=30, ge=1)
    max_snapshots_per_target: int = Field(default=100, ge=1)

    # ---- restore / PITR -------------------------------------------------------------

    restore_preview_sample_size: int = Field(default=50, ge=1)
    pitr_max_lookback_days: int = Field(default=35, ge=1)
    """A restore point older than this is outside what the retention
    policy guarantees WAL/transaction history for; requesting it is
    refused with the reason rather than attempting a recovery that can
    only fail partway through."""

    # ---- replication ----------------------------------------------------------------

    replication_lag_warning_seconds: float = Field(default=300.0, gt=0)
    replication_lag_critical_seconds: float = Field(default=1_800.0, gt=0)
    default_bandwidth_limit_mbps: float | None = Field(default=None, gt=0)

    # ---- disaster recovery / failover ------------------------------------------------

    failover_health_check_timeout_seconds: float = Field(default=30.0, gt=0)
    failover_health_check_retries: int = Field(default=3, ge=1)
    default_rpo_minutes: int = Field(default=60, ge=1)
    default_rto_minutes: int = Field(default=120, ge=1)

    # ---- runbooks ---------------------------------------------------------------------

    runbook_requires_approval: bool = Field(default=True)

    # ---- encryption / immutability --------------------------------------------------

    encryption_algorithm: str = Field(default="AES-256-GCM")
    key_rotation_days: int = Field(default=90, ge=1)
    default_retention_lock_days: int = Field(default=0, ge=0)
    """0 means no lock by default -- immutability is opt-in per policy,
    since a lock that cannot be shortened is a commitment the caller
    must make deliberately, never a default nobody chose."""

    # ---- retention ----------------------------------------------------------------------

    default_retention_days: int = Field(default=90, ge=1)
    default_archive_after_days: int = Field(default=30, ge=1)

    # ---- verification ---------------------------------------------------------------------

    verification_sample_restore_fraction: float = Field(default=0.05, ge=0.0, le=1.0)
    verification_max_age_days: int = Field(default=7, ge=1)
    """A backup nothing has verified in longer than this is treated as
    unverified for compliance reporting -- an integrity check that ran
    once at creation and never again is not an ongoing guarantee."""

    # ---- dr testing ------------------------------------------------------------------------

    dr_test_default_interval_days: int = Field(default=90, ge=1)

    # ---- workers ---------------------------------------------------------------------------

    workers_enabled: bool = Field(default=True)
    backup_scheduler_seconds: int = Field(default=60, ge=10, le=3_600)
    retention_sweep_seconds: int = Field(default=3_600, ge=60, le=604_800)
    verification_sweep_seconds: int = Field(default=3_600, ge=60, le=604_800)
    replication_monitor_seconds: int = Field(default=120, ge=10, le=3_600)
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
    service: BackupDrServiceSettings


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
        service=BackupDrServiceSettings(),
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
    "BackupDrServiceSettings",
    "Settings",
    "build_settings",
    "get_settings",
]
