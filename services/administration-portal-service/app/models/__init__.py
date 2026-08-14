"""Imports every model so ``Base.metadata`` sees every table."""

from __future__ import annotations

from app.models.admin import AdminAction, AdminSession
from app.models.api_management import ApiKey, ApiUsage
from app.models.diagnostics import Diagnostic, HealthCheck
from app.models.jobs import JobHistory, SystemJob
from app.models.maintenance import MaintenanceWindow, PlatformAnnouncement
from app.models.reporting import SystemAudit, SystemReport, SystemStatistic
from app.models.security import SecurityEvent, SecuritySetting
from app.models.settings import FeatureFlag, PlatformSetting, SystemConfiguration
from app.models.tenants import (
    Organization,
    Tenant,
    TenantHealth,
    TenantLimit,
    TenantProvisioning,
    TenantSetting,
    TenantUsage,
)

__all__ = [
    "AdminAction",
    "AdminSession",
    "ApiKey",
    "ApiUsage",
    "Diagnostic",
    "FeatureFlag",
    "HealthCheck",
    "JobHistory",
    "MaintenanceWindow",
    "Organization",
    "PlatformAnnouncement",
    "PlatformSetting",
    "SecurityEvent",
    "SecuritySetting",
    "SystemAudit",
    "SystemConfiguration",
    "SystemJob",
    "SystemReport",
    "SystemStatistic",
    "Tenant",
    "TenantHealth",
    "TenantLimit",
    "TenantProvisioning",
    "TenantSetting",
    "TenantUsage",
]
