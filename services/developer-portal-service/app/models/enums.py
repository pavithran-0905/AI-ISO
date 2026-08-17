"""Enumerations for the Developer Portal service.

Every enum here is a :class:`~enum.StrEnum` -- stored as its literal
string value in Postgres (plain ``String`` columns, matching every
other AI-IOS service's convention), and comparable with ``==`` against
a value freshly loaded from the database, which comes back as a plain
``str`` rather than the enum instance itself. See
``services/mobile-api-service``'s and
``services/public-api-platform``'s own hard-won lessons on why ``is``
comparison, and even bare ``.value`` access, on such a value is unsafe
-- coerce through the enum class first (``EnumClass(value)``).
"""

from __future__ import annotations

from enum import StrEnum


class DeveloperSessionStatus(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


class ContentStatus(StrEnum):
    """Shared publication lifecycle for documentation pages, tutorials,
    and learning paths -- see ``app.documentation.engine`` for the
    transition table this drives."""

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class FeedbackSentiment(StrEnum):
    HELPFUL = "helpful"
    NOT_HELPFUL = "not_helpful"


class TutorialDifficulty(StrEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class SampleProjectCategory(StrEnum):
    REFERENCE = "reference"
    STARTER = "starter"
    INTEGRATION = "integration"
    INFRASTRUCTURE = "infrastructure"
    AUTOMATION = "automation"
    AI = "ai"
    CONTAINER = "container"
    DEPLOYMENT = "deployment"


class PlaygroundExampleType(StrEnum):
    REST = "rest"
    GRAPHQL = "graphql"
    SDK = "sdk"
    WORKFLOW = "workflow"
    PROMPT = "prompt"
    PLUGIN = "plugin"


class PlaygroundSessionStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    EXPIRED = "expired"


class WebhookTestStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class PluginSubmissionStatus(StrEnum):
    """A plugin submission's position in its own publishing workflow --
    see ``app.plugins.engine`` for the transition table this drives."""

    SUBMITTED = "submitted"
    VALIDATING = "validating"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"


class PluginReviewDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    CHANGES_REQUESTED = "changes_requested"


class CommunityPostType(StrEnum):
    QUESTION = "question"
    DISCUSSION = "discussion"


class CommunityPostStatus(StrEnum):
    """A community post's position in its own lifecycle -- see
    ``app.community.engine`` for the transition table this drives."""

    OPEN = "open"
    ANSWERED = "answered"
    CLOSED = "closed"


class ModerationStatus(StrEnum):
    VISIBLE = "visible"
    HIDDEN = "hidden"
    FLAGGED = "flagged"


class KnowledgeArticleCategory(StrEnum):
    TECHNICAL = "technical"
    TROUBLESHOOTING = "troubleshooting"
    BEST_PRACTICES = "best_practices"
    ARCHITECTURE = "architecture"
    OPERATIONS = "operations"
    MIGRATION = "migration"
    SECURITY = "security"


class SearchContentType(StrEnum):
    DOCUMENTATION = "documentation"
    TUTORIAL = "tutorial"
    SAMPLE = "sample"
    PLUGIN = "plugin"
    KNOWLEDGE = "knowledge"


class ReportKind(StrEnum):
    PORTAL_USAGE = "portal_usage"
    DEVELOPER_ACTIVITY = "developer_activity"
    SDK = "sdk"
    DOCUMENTATION = "documentation"
    SEARCH = "search"
    LEARNING = "learning"
    COMMUNITY = "community"
    AUDIT = "audit"


class ReportFormat(StrEnum):
    JSON = "json"
    PDF = "pdf"
    CSV = "csv"


class ReportStatus(StrEnum):
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class PortalAuditAction(StrEnum):
    """What was done, for the immutable developer portal audit trail."""

    DOCUMENTATION_CHANGE = "documentation_change"
    PLUGIN_PUBLICATION = "plugin_publication"
    ADMINISTRATIVE = "administrative"
    COMMUNITY_MODERATION = "community_moderation"
    KNOWLEDGE_UPDATE = "knowledge_update"
    PORTAL_CONFIGURATION = "portal_configuration"


__all__ = [
    "CommunityPostStatus",
    "CommunityPostType",
    "ContentStatus",
    "DeveloperSessionStatus",
    "FeedbackSentiment",
    "KnowledgeArticleCategory",
    "ModerationStatus",
    "PlaygroundExampleType",
    "PlaygroundSessionStatus",
    "PluginReviewDecision",
    "PluginSubmissionStatus",
    "PortalAuditAction",
    "ReportFormat",
    "ReportKind",
    "ReportStatus",
    "SampleProjectCategory",
    "SearchContentType",
    "TutorialDifficulty",
    "WebhookTestStatus",
]
