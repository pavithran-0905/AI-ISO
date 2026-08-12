"""Document intelligence service settings.

Composes ``shared_core.config``'s aggregate settings with the fields
specific to this service: host/port, CORS, JWT verification key, OCR
engine selection and language, layout and extraction thresholds,
classification and validation policy, review routing, and the worker
intervals.

**This service holds no model-provider credential.** Classification,
entity extraction, and summarization are implemented as deterministic
engines -- rules, patterns, and extractive scoring -- not as calls to a
hosted model. That is not a limitation worked around; it is what the
spec's own DO NOT IMPLEMENT list requires ("Third-party SaaS OCR
Dependencies") extended to its logical conclusion: a document
intelligence service whose every output depends on an API key is one that
cannot be tested, cannot be audited, and cannot run in an air-gapped
deployment. Where a model would genuinely do better -- abstractive
summarization, semantic classification -- the seam is declared and the
deterministic path is what ships.
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


class DocumentIntelligenceServiceSettings(BaseSettings):
    """Fields specific to this service, not covered by any shared_core section."""

    model_config = SettingsConfigDict(
        env_prefix="AIIOS_DOCUMENT_INTELLIGENCE_SERVICE_", env_file=".env", extra="ignore"
    )

    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8034, ge=1, le=65_535)
    cors_allowed_origins: list[str] = Field(default_factory=list)
    jwt_public_key_path: str = Field(default="keys/jwt_public_key.pem")

    # ---- platform integrations this service reaches live -------------------

    rag_service_base_url: str = Field(default="http://localhost:8033")
    workflow_service_base_url: str = Field(default="http://localhost:8021")
    notification_center_base_url: str = Field(default="http://localhost:8025")

    http_client_timeout_seconds: float = Field(default=30.0, gt=0)

    # ---- ingestion ---------------------------------------------------------

    max_document_bytes: int = Field(default=52_428_800, ge=1)
    storage_bucket: str = Field(default="aiios-documents")
    """The MinIO bucket original document bytes are written to.

    Original bytes, not extracted text: text is what parsing produced, so
    a service that kept only text could never run a document's first
    parse -- and every later run would be a re-parse of a previous parse
    rather than of the document."""
    """50 MiB. Parsing and OCR both run in memory, so this is the real
    bound on what one upload can cost the process."""
    max_pages_per_document: int = Field(default=2_000, ge=1)
    """A page is the unit OCR and layout analysis are charged in. A
    thousand-page scan is a legitimate document and also the one that
    will exhaust a worker, so the ceiling is explicit rather than
    discovered."""
    max_archive_members: int = Field(default=200, ge=1)
    """Members extracted from one ZIP. A zip bomb expands to far more
    than its own size, and refusing on the member count catches it before
    any member is written."""

    # ---- OCR ----------------------------------------------------------------

    ocr_enabled: bool = Field(default=True)
    ocr_engine: str = Field(default="tesseract")
    """Which engine backs OCR. ``tesseract`` is the only implementation;
    see :mod:`app.ocr.registry` for what adding another requires."""
    ocr_languages: list[str] = Field(default_factory=lambda: ["eng"])
    ocr_minimum_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    """Words below this confidence are dropped. Zero by default: a
    threshold tuned on clean scans silently deletes most of a poor one,
    and a partly-wrong page is more useful than a blank one."""
    ocr_timeout_seconds: float = Field(default=120.0, gt=0)
    ocr_dpi: int = Field(default=300, ge=72, le=1_200)

    # ---- layout --------------------------------------------------------------

    layout_header_band: float = Field(default=0.08, ge=0.0, le=0.5)
    layout_footer_band: float = Field(default=0.08, ge=0.0, le=0.5)
    """Fraction of page height treated as header/footer. Bands rather
    than content matching: a header is defined by where it sits, and
    matching on repeated text misses the first page and catches a running
    quotation."""
    layout_column_gap_ratio: float = Field(default=0.05, ge=0.0, le=1.0)

    # ---- classification --------------------------------------------------------

    classification_minimum_confidence: float = Field(default=0.35, ge=0.0, le=1.0)
    classification_multi_label: bool = Field(default=True)
    """A contract that is also an invoice is both, and forcing a single
    label loses whichever one the router needed."""
    auto_route_enabled: bool = Field(default=True)

    # ---- extraction -------------------------------------------------------------

    entity_minimum_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    table_minimum_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    form_minimum_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    max_entities_per_document: int = Field(default=5_000, ge=1)

    # ---- summarization and translation ---------------------------------------------

    summary_sentence_count: int = Field(default=5, ge=1, le=100)
    summary_bullet_count: int = Field(default=7, ge=1, le=100)
    translation_enabled: bool = Field(default=True)
    default_target_language: str = Field(default="en")

    # ---- validation and review -------------------------------------------------------

    validation_minimum_completeness: float = Field(default=0.8, ge=0.0, le=1.0)
    duplicate_similarity_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    """Jaccard similarity at which two documents are near-duplicates.

    Chosen against the three-word shingle size the validation engine uses,
    not picked for looking strict: one changed word invalidates *k*
    shingles on each side, so a re-scan of the same page differing by a
    single OCR error tops out around 0.81. A 0.92 threshold would never
    fire on the one case near-duplicate detection exists for, while two
    different forms sharing a template score about 0.12."""
    review_required_below_confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    """Below this, a human reviews it. The whole point of a confidence
    score is that something acts on it; a service that computes one and
    routes everything identically has measured nothing."""
    review_sla_seconds: int = Field(default=86_400, ge=60)

    # ---- workers ---------------------------------------------------------------------

    workers_enabled: bool = Field(default=True)
    processing_sweep_seconds: int = Field(default=30, ge=5, le=3_600)
    review_expiry_sweep_seconds: int = Field(default=900, ge=30, le=86_400)
    statistics_rollup_seconds: int = Field(default=900, ge=60, le=86_400)
    retention_sweep_seconds: int = Field(default=3_600, ge=60, le=604_800)


@dataclass(frozen=True, slots=True)
class Settings:
    """Every configuration section this service actually uses."""

    application: ApplicationSettings
    database: DatabaseSettings
    redis: RedisSettings
    rabbitmq: RabbitMQSettings
    email: EmailSettings
    minio: MinioSettings
    service: DocumentIntelligenceServiceSettings


def build_settings() -> Settings:
    """Assemble the settings this service uses.

    The shared sections come from ``shared_core``'s cached accessor, so
    every service in one process sees the same database and cache
    configuration. This service's own section is constructed fresh --
    it is not part of that cache.
    """
    shared = get_shared_settings()
    return Settings(
        application=shared.application,
        database=shared.database,
        redis=shared.redis,
        rabbitmq=shared.rabbitmq,
        email=shared.email,
        minio=shared.minio,
        service=DocumentIntelligenceServiceSettings(),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """The process-wide settings, built once.

    Cached because settings are read on every request through the
    dependency graph and constructing them re-reads the environment.
    Tests that need different values must call ``cache_clear()`` both
    before and after -- before so their own values are seen, after so the
    next test does not inherit them.
    """
    return build_settings()


__all__ = [
    "DocumentIntelligenceServiceSettings",
    "Settings",
    "build_settings",
    "get_settings",
]
