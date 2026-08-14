"""License & billing service settings.

Composes ``shared_core.config``'s aggregate settings with the fields
specific to this service: host/port, CORS, JWT verification key,
licensing/metering/billing/quota thresholds.

**Every threshold a commercial decision depends on is configuration,
not a constant.** A grace period, a quota burst allowance, or an
invoice due window compiled into the code is one a deployment cannot
tune to its own commercial terms without a release.
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


class LicenseBillingServiceSettings(BaseSettings):
    """Fields specific to this service, not covered by any shared_core section."""

    model_config = SettingsConfigDict(
        env_prefix="AIIOS_LICENSE_BILLING_SERVICE_", env_file=".env", extra="ignore"
    )

    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8040, ge=1, le=65_535)
    cors_allowed_origins: list[str] = Field(default_factory=list)
    jwt_public_key_path: str = Field(default="keys/jwt_public_key.pem")

    # ---- subscriptions / renewals -----------------------------------------------------------

    subscription_grace_period_days: int = Field(default=7, ge=0)
    renewal_reminder_days_before: int = Field(default=14, ge=1)
    trial_expiring_reminder_days_before: int = Field(default=3, ge=1)

    # ---- licenses -------------------------------------------------------------------------

    license_expiring_reminder_days_before: int = Field(default=14, ge=1)
    offline_license_max_validity_days: int = Field(default=365, ge=1)

    # ---- quotas / usage -----------------------------------------------------------------------

    quota_alert_warning_fraction: float = Field(default=0.8, ge=0.0, le=1.0)
    quota_burst_grace_fraction: float = Field(default=0.1, ge=0.0, le=1.0)

    # ---- billing / payments -------------------------------------------------------------------

    invoice_due_days: int = Field(default=30, ge=1)
    payment_retry_max_attempts: int = Field(default=3, ge=1)

    # ---- workers ------------------------------------------------------------------------------

    workers_enabled: bool = Field(default=True)
    subscription_renewal_sweep_seconds: int = Field(default=3_600, ge=60, le=604_800)
    license_expiry_sweep_seconds: int = Field(default=3_600, ge=60, le=604_800)
    quota_reset_sweep_seconds: int = Field(default=900, ge=60, le=86_400)
    invoice_generation_sweep_seconds: int = Field(default=3_600, ge=60, le=604_800)
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
    service: LicenseBillingServiceSettings


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
        service=LicenseBillingServiceSettings(),
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
    "LicenseBillingServiceSettings",
    "Settings",
    "build_settings",
    "get_settings",
]
