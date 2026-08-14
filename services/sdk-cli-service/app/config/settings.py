"""SDK & CLI service settings.

Composes ``shared_core.config``'s aggregate settings with the fields
specific to this service: host/port, CORS, JWT verification key, and
version-deprecation/session/statistics thresholds.

**Every threshold a release or session decision depends on is
configuration, not a constant.** A deprecation warning window or a CLI
session lifetime compiled into the code is one a deployment cannot tune
to its own release cadence without shipping a new build of this
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


class SdkCliServiceSettings(BaseSettings):
    """Fields specific to this service, not covered by any shared_core section."""

    model_config = SettingsConfigDict(
        env_prefix="AIIOS_SDK_CLI_SERVICE_", env_file=".env", extra="ignore"
    )

    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8042, ge=1, le=65_535)
    cors_allowed_origins: list[str] = Field(default_factory=list)
    jwt_public_key_path: str = Field(default="keys/jwt_public_key.pem")

    # ---- versioning / deprecation ---------------------------------------------------------

    sdk_deprecation_warning_days_before: int = Field(default=90, ge=1)
    cli_deprecation_warning_days_before: int = Field(default=90, ge=1)

    # ---- CLI sessions ---------------------------------------------------------------------

    cli_session_max_age_minutes: int = Field(default=720, ge=1)

    # ---- plugins ----------------------------------------------------------------------------

    plugin_update_check_enabled: bool = Field(default=True)

    # ---- workers ------------------------------------------------------------------------------

    workers_enabled: bool = Field(default=True)
    version_compatibility_sweep_seconds: int = Field(default=3_600, ge=60, le=604_800)
    cli_update_check_sweep_seconds: int = Field(default=3_600, ge=60, le=604_800)
    plugin_update_sweep_seconds: int = Field(default=3_600, ge=60, le=604_800)
    session_expiry_sweep_seconds: int = Field(default=300, ge=60, le=86_400)
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
    service: SdkCliServiceSettings


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
        service=SdkCliServiceSettings(),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """The process-wide settings.

    Cached, so a test that changes the environment must call
    ``get_settings.cache_clear()`` both before *and* after -- before to
    pick its change up, after so it does not leak into the next test.
    """
    return build_settings()


__all__ = ["SdkCliServiceSettings", "Settings", "build_settings", "get_settings"]
