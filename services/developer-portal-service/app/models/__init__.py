"""Imports every model so ``Base.metadata`` sees every table."""

from __future__ import annotations

from app.models.community import CommunityComment, CommunityPost
from app.models.developers import (
    DeveloperBookmark,
    DeveloperFavorite,
    DeveloperProfile,
    DeveloperSession,
)
from app.models.documentation import DocumentationFeedback, DocumentationPage, DocumentationVersion
from app.models.explorer import GraphQlQuery, PlaygroundSession, WebhookTest
from app.models.knowledge import KnowledgeArticle, SearchIndexEntry
from app.models.learning import LearningPath, Tutorial
from app.models.plugins import PluginReview, PluginSubmission
from app.models.reporting import PortalAudit, PortalReport, PortalStatistic
from app.models.samples import CodeSnippet, SampleProject
from app.models.sdk import SdkDownload

__all__ = [
    "CodeSnippet",
    "CommunityComment",
    "CommunityPost",
    "DeveloperBookmark",
    "DeveloperFavorite",
    "DeveloperProfile",
    "DeveloperSession",
    "DocumentationFeedback",
    "DocumentationPage",
    "DocumentationVersion",
    "GraphQlQuery",
    "KnowledgeArticle",
    "LearningPath",
    "PlaygroundSession",
    "PluginReview",
    "PluginSubmission",
    "PortalAudit",
    "PortalReport",
    "PortalStatistic",
    "SampleProject",
    "SdkDownload",
    "SearchIndexEntry",
    "Tutorial",
    "WebhookTest",
]
