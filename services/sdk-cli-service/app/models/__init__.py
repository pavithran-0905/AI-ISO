"""Imports every model so ``Base.metadata`` sees every table."""

from __future__ import annotations

from app.models.cli import CliPlugin, CliProfile, CliSession, CliUpdate, CliUsage, CliVersion
from app.models.reporting import CliReport, CliStatistic, SdkAudit
from app.models.sdk import SdkDownload, SdkLanguageCatalog, SdkPackage, SdkRelease, SdkVersion

__all__ = [
    "CliPlugin",
    "CliProfile",
    "CliReport",
    "CliSession",
    "CliStatistic",
    "CliUpdate",
    "CliUsage",
    "CliVersion",
    "SdkAudit",
    "SdkDownload",
    "SdkLanguageCatalog",
    "SdkPackage",
    "SdkRelease",
    "SdkVersion",
]
