"""Observability platform service settings.

Composes ``shared_core.config``'s aggregate settings with the fields
specific to this service: host/port, CORS, JWT verification key, ingestion
limits and clock-skew tolerance, retention tiers, and the thresholds every
analytical engine is governed by.

**Every threshold an engine uses is configuration, not a constant.** An
anomaly detector whose sensitivity is compiled in is one that gets turned
off wholesale the first time it is too noisy for a particular metric,
which loses the signal along with the noise. The defaults here are the
ones the engines' own docstrings justify; a deployment that disagrees
should be able to say so without a release.

**No model-provider credential.** Anomaly detection, root cause analysis
and forecasting are deterministic and auditable, which the spec's DO NOT
IMPLEMENT list ("Commercial Observability SaaS") requires and which an
operator being woken at 3am deserves. Where a model would genuinely add
something, the seam is declared and the deterministic path is what ships.
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
)


class ObservabilityPlatformServiceSettings(BaseSettings):
    """Fields specific to this service, not covered by any shared_core section."""

    model_config = SettingsConfigDict(
        env_prefix="AIIOS_OBSERVABILITY_PLATFORM_SERVICE_", env_file=".env", extra="ignore"
    )

    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8035, ge=1, le=65_535)
    cors_allowed_origins: list[str] = Field(default_factory=list)
    jwt_public_key_path: str = Field(default="keys/jwt_public_key.pem")

    # ---- platform integrations this service reaches live ---------------------------

    notification_center_base_url: str = Field(default="http://localhost:8025")
    knowledge_graph_base_url: str = Field(default="http://localhost:8018")
    incident_service_base_url: str = Field(default="http://localhost:8013")
    http_client_timeout_seconds: float = Field(default=30.0, gt=0)

    # ---- ingestion -----------------------------------------------------------------

    max_batch_size: int = Field(default=10_000, ge=1)
    """Signals accepted in one request. A batch larger than this is
    rejected with its size rather than truncated: a client that thinks it
    sent twelve thousand spans and had two thousand silently dropped has a
    trace graph with holes it cannot see."""

    max_label_count: int = Field(default=64, ge=1)
    max_label_value_length: int = Field(default=1_024, ge=1)
    """Label cardinality is the classic way a metrics store dies. A label
    whose value is a request id turns one series into millions, and the
    limit that stops it has to be at ingest -- afterwards the damage is
    already stored."""

    max_log_message_length: int = Field(default=64_000, ge=256)
    max_spans_per_trace: int = Field(default=10_000, ge=1)

    clock_skew_tolerance_seconds: float = Field(default=300.0, ge=0)
    """How far into the future a timestamp may be before it is clamped.
    Client clocks are wrong, sometimes badly, and a span claiming to end
    next Tuesday corrupts every duration and every window it lands in."""

    max_ingest_age_days: int = Field(default=30, ge=1)
    """Older than this and a backfilled signal is rejected. Accepting it
    would silently rewrite a window somebody has already reported on."""

    # ---- retention -------------------------------------------------------------------

    default_raw_retention_days: int = Field(default=7, ge=1)
    default_downsampled_retention_days: int = Field(default=30, ge=1)
    default_coarse_retention_days: int = Field(default=395, ge=1)
    """Just over thirteen months, so a year-on-year comparison has both
    endpoints. Exactly 365 deletes last year's same-week figure on the day
    it is wanted."""
    downsample_interval_seconds: int = Field(default=300, ge=1)
    retention_batch_size: int = Field(default=10_000, ge=1)

    # ---- SLO -------------------------------------------------------------------------

    default_slo_window_days: int = Field(default=30, ge=1)
    slo_at_risk_budget_fraction: float = Field(default=0.25, ge=0.0, le=1.0)
    """Below this share of error budget remaining, an SLO is AT_RISK. A
    binary healthy/breaching gives no warning while there is still time to
    act, which is the entire point of a budget."""

    fast_burn_hours: float = Field(default=1.0, gt=0)
    fast_burn_threshold: float = Field(default=14.4, gt=0)
    slow_burn_hours: float = Field(default=6.0, gt=0)
    slow_burn_threshold: float = Field(default=6.0, gt=0)
    """Google's SRE workbook figures for a 30-day window: 14.4x over an
    hour exhausts a month's budget in about two days, 6x over six hours in
    about five. Both must fire together -- the fast window alone pages on
    every blip, the slow one alone takes hours to notice an outage."""

    min_sli_sample_count: int = Field(default=1, ge=0)
    """Below this many requests in a window, the SLI is NO_DATA rather
    than a ratio. One request that failed is not a 0% availability
    service."""

    # ---- anomaly detection --------------------------------------------------------------

    anomaly_min_history_points: int = Field(default=30, ge=3)
    """Fewer points than this and no statistical claim is honest. The
    engine says so rather than producing a detection from six samples."""

    anomaly_robust_z_threshold: float = Field(default=3.5, gt=0)
    """Robust z-score (median + MAD) above which a point is anomalous.
    3.5 rather than 3.0 because MAD-based scores are heavier-tailed on
    real infrastructure metrics, and 3.0 produces steady false positives
    on any metric with a daily shape."""

    anomaly_seasonal_min_cycles: int = Field(default=3, ge=2)
    """Complete cycles of history required before a seasonal comparison is
    made. Two is enough to see a pattern and not enough to distinguish it
    from a coincidence."""

    anomaly_spike_recovery_points: int = Field(default=2, ge=1)
    anomaly_level_shift_min_points: int = Field(default=5, ge=2)
    """A deviation sustained for this many points is a level shift rather
    than a spike, and the two need different responses."""

    anomaly_exclude_recent_for_baseline: bool = Field(default=True)
    """Whether to exclude the point under test, and its immediate
    neighbours, from the baseline it is compared against. Without this a
    sustained outage shifts the median until the outage stops looking
    anomalous -- the detector learns the incident as normal."""

    # ---- capacity forecasting -----------------------------------------------------------

    forecast_min_history_points: int = Field(default=14, ge=3)
    forecast_min_r_squared: float = Field(default=0.3, ge=0.0, le=1.0)
    """Below this fit, the engine refuses rather than returning a line
    through noise. A forecast nobody should act on is worse than no
    forecast, because it looks like one."""
    forecast_default_horizon_days: int = Field(default=30, ge=1)
    forecast_max_horizon_days: int = Field(default=365, ge=1)
    forecast_interval_z: float = Field(default=1.96, gt=0)
    """The multiplier on the prediction standard error, for a 95%
    interval. Configurable because a capacity decision may want a wider
    one, and the number should be visible rather than buried."""

    # ---- root cause analysis --------------------------------------------------------------

    rca_correlation_window_seconds: float = Field(default=900.0, gt=0)
    """How far before an incident a candidate signal may sit and still be
    considered. Wide enough for a slow-burning cause, narrow enough that
    the whole day is not a candidate."""

    rca_min_precedence_seconds: float = Field(default=0.0, ge=0)
    rca_max_graph_depth: int = Field(default=6, ge=1)
    """Traversal bound. Real dependency graphs contain cycles, and this is
    the backstop that makes every traversal terminate regardless."""
    rca_max_candidates: int = Field(default=10, ge=1)
    rca_indistinguishable_margin: float = Field(default=0.05, ge=0.0)
    """Two candidates whose scores differ by less than this are reported
    as indistinguishable rather than ranked. A confident wrong answer
    sends somebody to fix the wrong thing."""

    # ---- topology ----------------------------------------------------------------------------

    topology_stale_after_hours: float = Field(default=24.0, gt=0)
    topology_min_calls_for_confidence: int = Field(default=100, ge=1)
    """Calls at which an inferred edge is fully trusted. Below it,
    confidence scales -- an edge seen once in a retry path is not the same
    claim as one seen a million times."""

    # ---- cost ---------------------------------------------------------------------------------

    cost_currency: str = Field(default="USD", min_length=3, max_length=3)
    cost_rate_card_version: str = Field(default="default-v1")
    """Which prices produced a report. Without it, a report cannot be
    reproduced after a price change and two reports cannot be compared."""
    cost_allocate_shared: bool = Field(default=True)
    cost_shared_allocation_basis: str = Field(default="usage")

    # ---- search --------------------------------------------------------------------------------

    max_query_range_days: int = Field(default=90, ge=1)
    max_query_results: int = Field(default=1_000, ge=1)
    query_timeout_seconds: float = Field(default=30.0, gt=0)

    # ---- workers ---------------------------------------------------------------------------------

    workers_enabled: bool = Field(default=True)
    slo_evaluation_seconds: int = Field(default=60, ge=10, le=3_600)
    anomaly_sweep_seconds: int = Field(default=300, ge=30, le=3_600)
    topology_rebuild_seconds: int = Field(default=600, ge=60, le=86_400)
    retention_sweep_seconds: int = Field(default=3_600, ge=60, le=604_800)
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
    service: ObservabilityPlatformServiceSettings


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
        service=ObservabilityPlatformServiceSettings(),
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
    "ObservabilityPlatformServiceSettings",
    "Settings",
    "build_settings",
    "get_settings",
]
