"""Imports every model so ``Base.metadata`` sees every table."""

from __future__ import annotations

from app.models.applications import ApplicationCredential, DeveloperApplication
from app.models.credentials import ApiKey, OAuthClient, OAuthToken, PersonalAccessToken
from app.models.developers import DeveloperAccount, DeveloperOrganization
from app.models.documents import ApiChangelogEntry, ApiVersion, GraphQlSchema, OpenApiDocument
from app.models.products import ApiPlan, ApiProduct, ApiSubscription
from app.models.reporting import DeveloperAudit, DeveloperReport, DeveloperStatistic
from app.models.sandbox import ApiMockService, ApiSandboxSession
from app.models.usage import ApiQuota, ApiRateLimit, ApiUsageEvent

__all__ = [
    "ApiChangelogEntry",
    "ApiKey",
    "ApiMockService",
    "ApiPlan",
    "ApiProduct",
    "ApiQuota",
    "ApiRateLimit",
    "ApiSandboxSession",
    "ApiSubscription",
    "ApiUsageEvent",
    "ApiVersion",
    "ApplicationCredential",
    "DeveloperAccount",
    "DeveloperApplication",
    "DeveloperAudit",
    "DeveloperOrganization",
    "DeveloperReport",
    "DeveloperStatistic",
    "GraphQlSchema",
    "OAuthClient",
    "OAuthToken",
    "OpenApiDocument",
    "PersonalAccessToken",
]
