"""The 12 docs/071 REST endpoints.

**Every route derives its tenant from the token.** No query or body
parameter names an organization; see
:func:`app.api.deps.get_organization_id` for why that is not a
convenience.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from shared_core.exceptions.conflict import ConflictError
from shared_core.exceptions.validation import ValidationError
from shared_core.logging.context import get_log_context

from app.api.deps import (
    CliPluginServiceDep,
    CliUpdateServiceDep,
    CodeGenerationServiceDep,
    CurrentUserId,
    OrganizationId,
    Repos,
    SdkReleaseServiceDep,
    SdkVersionServiceDep,
    require_administrator,
)
from app.generator.engine import FieldSpec
from app.models.cli import CliPlugin, CliUpdate, CliVersion
from app.models.enums import PluginStatus, ReleaseStatus
from app.models.reporting import CliReport
from app.models.sdk import SdkDownload, SdkLanguageCatalog, SdkRelease
from app.schemas.response import ResponseMeta, SuccessResponse
from app.schemas.sdk_cli import (
    MAX_PAGE_SIZE,
    CliPluginResponse,
    CliUpdateRequest,
    CliUpdateResponse,
    CliVersionResponse,
    CliVersionsResponse,
    GeneratedArtifactResponse,
    PluginInstallRequest,
    PluginRemoveRequest,
    ReportResponse,
    ReportsResponse,
    SdkDownloadResponse,
    SdkDownloadsResponse,
    SdkGenerateRequest,
    SdkGenerateResponse,
    SdkLanguageResponse,
    SdkReleaseResponse,
    SdkReleasesResponse,
    SdkResponse,
    StatisticsResponse,
    StatisticWindowResponse,
)
from app.services.cli_plugins import TransitionRefusedError as PluginTransitionRefusedError
from app.services.generator import ModelSpec

router = APIRouter(tags=["SDK & CLI"])

_INSTALL_SOURCE_STATUSES = frozenset({PluginStatus.AVAILABLE, PluginStatus.REMOVED})


def _meta() -> ResponseMeta:
    return ResponseMeta(request_id=get_log_context().request_id or "unknown")


def _default_window(days: int) -> tuple[datetime, datetime]:
    end = datetime.now(UTC)
    return end - timedelta(days=days), end


def _sdk_language_response(entry: SdkLanguageCatalog) -> SdkLanguageResponse:
    return SdkLanguageResponse(
        id=entry.id,
        language=entry.language,
        display_name=entry.display_name,
        is_enabled=entry.is_enabled,
        latest_version_id=entry.latest_version_id,
    )


def _sdk_release_response(release: SdkRelease) -> SdkReleaseResponse:
    return SdkReleaseResponse(
        id=release.id,
        sdk_version_id=release.sdk_version_id,
        status=release.status,
        release_notes=release.release_notes,
        breaking_changes=release.breaking_changes,
        published_at=release.published_at,
    )


def _sdk_download_response(download: SdkDownload) -> SdkDownloadResponse:
    return SdkDownloadResponse(
        id=download.id,
        sdk_version_id=download.sdk_version_id,
        downloaded_at=download.downloaded_at,
        source_ip=download.source_ip,
    )


def _cli_version_response(version: CliVersion) -> CliVersionResponse:
    return CliVersionResponse(
        id=version.id,
        version=version.version_label,
        api_compatibility_version=version.api_compatibility_version,
        is_enabled=version.is_enabled,
        released_at=version.released_at,
        deprecated_at=version.deprecated_at,
    )


def _cli_update_response(update: CliUpdate) -> CliUpdateResponse:
    return CliUpdateResponse(
        id=update.id,
        from_version=update.from_version,
        to_version=update.to_version,
        status=update.status,
        checked_at=update.checked_at,
        applied_at=update.applied_at,
    )


def _cli_plugin_response(plugin: CliPlugin) -> CliPluginResponse:
    return CliPluginResponse(
        id=plugin.id,
        name=plugin.name,
        version=plugin.version_label,
        status=plugin.status,
        is_signed=plugin.is_signed,
        marketplace_ref=plugin.marketplace_ref,
    )


def _report_response(report: CliReport) -> ReportResponse:
    return ReportResponse(
        id=report.id,
        kind=report.kind,
        report_format=report.report_format,
        title=report.title,
        status=report.status,
        period_start=report.period_start,
        period_end=report.period_end,
        generated_at=report.generated_at,
        row_count=report.row_count,
    )


# ---- GET /sdk ---------------------------------------------------------------------------------


@router.get(
    "/sdk", response_model=SuccessResponse[SdkResponse], summary="List supported SDK languages"
)
async def list_sdk_languages(
    organization_id: OrganizationId, repos: Repos
) -> SuccessResponse[SdkResponse]:
    rows = await repos.sdk_languages.list_all(organization_id)
    data = SdkResponse(languages=[_sdk_language_response(row) for row in rows], total=len(rows))
    return SuccessResponse(message="SDK languages retrieved.", data=data, meta=_meta())


# ---- GET /sdk/releases ---------------------------------------------------------------------


@router.get(
    "/sdk/releases",
    response_model=SuccessResponse[SdkReleasesResponse],
    summary="List SDK releases",
)
async def list_sdk_releases(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[SdkReleasesResponse]:
    rows = await repos.sdk_releases.list_recent(organization_id, limit=limit)
    data = SdkReleasesResponse(
        releases=[_sdk_release_response(row) for row in rows], total=len(rows)
    )
    return SuccessResponse(message="SDK releases retrieved.", data=data, meta=_meta())


# ---- GET /sdk/downloads ---------------------------------------------------------------------


@router.get(
    "/sdk/downloads",
    response_model=SuccessResponse[SdkDownloadsResponse],
    summary="List SDK downloads",
)
async def list_sdk_downloads(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[SdkDownloadsResponse]:
    rows = await repos.sdk_downloads.list_recent(organization_id, limit=limit)
    data = SdkDownloadsResponse(
        downloads=[_sdk_download_response(row) for row in rows], total=len(rows)
    )
    return SuccessResponse(message="SDK downloads retrieved.", data=data, meta=_meta())


# ---- POST /sdk/generate ---------------------------------------------------------------------


@router.post(
    "/sdk/generate",
    response_model=SuccessResponse[SdkGenerateResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Generate and publish an SDK version",
    dependencies=[Depends(require_administrator)],
)
async def generate_sdk(
    organization_id: OrganizationId,
    version_service: SdkVersionServiceDep,
    release_service: SdkReleaseServiceDep,
    generation_service: CodeGenerationServiceDep,
    body: SdkGenerateRequest,
    actor: CurrentUserId,
) -> SuccessResponse[SdkGenerateResponse]:
    try:
        artifacts = generation_service.generate_models(
            body.language,
            [
                ModelSpec(
                    class_name=model.class_name,
                    fields=[
                        FieldSpec(name=field.name, type_name=field.type_name)
                        for field in model.fields
                    ],
                )
                for model in body.models
            ],
        )
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc

    sdk_version = await version_service.create_version(
        organization_id,
        language=body.language,
        version=body.version,
        api_compatibility_version=body.api_compatibility_version,
    )
    release = await release_service.create_draft(
        organization_id,
        sdk_version_id=sdk_version.id,
        release_notes=body.release_notes,
        breaking_changes=body.breaking_changes,
    )
    now = datetime.now(UTC)
    release = await release_service.transition(
        release,
        target=ReleaseStatus.PUBLISHED,
        language=body.language,
        version=body.version,
        actor_id=actor,
        now=now,
    )

    data = SdkGenerateResponse(
        sdk_version_id=sdk_version.id,
        sdk_release_id=release.id,
        artifacts=[
            GeneratedArtifactResponse(class_name=artifact.class_name, source=artifact.source)
            for artifact in artifacts
        ],
    )
    return SuccessResponse(message="SDK generated and published.", data=data, meta=_meta())


# ---- GET /cli, GET /cli/releases ---------------------------------------------------------------


@router.get(
    "/cli", response_model=SuccessResponse[CliVersionsResponse], summary="List CLI versions"
)
async def list_cli_versions(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[CliVersionsResponse]:
    rows = await repos.cli_versions.list_recent(organization_id, limit=limit)
    data = CliVersionsResponse(
        versions=[_cli_version_response(row) for row in rows], total=len(rows)
    )
    return SuccessResponse(message="CLI versions retrieved.", data=data, meta=_meta())


@router.get(
    "/cli/releases",
    response_model=SuccessResponse[CliVersionsResponse],
    summary="List CLI releases",
)
async def list_cli_releases(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[CliVersionsResponse]:
    rows = await repos.cli_versions.list_recent(organization_id, limit=limit)
    data = CliVersionsResponse(
        versions=[_cli_version_response(row) for row in rows], total=len(rows)
    )
    return SuccessResponse(message="CLI releases retrieved.", data=data, meta=_meta())


# ---- POST /cli/update ---------------------------------------------------------------------


@router.post(
    "/cli/update",
    response_model=SuccessResponse[CliUpdateResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Record a CLI update attempt",
    dependencies=[Depends(require_administrator)],
)
async def update_cli(
    organization_id: OrganizationId, update_service: CliUpdateServiceDep, body: CliUpdateRequest
) -> SuccessResponse[CliUpdateResponse]:
    update = await update_service.attempt_update(
        organization_id,
        from_version=body.from_version,
        to_version=body.to_version,
        succeeded=body.succeeded,
        now=datetime.now(UTC),
    )
    return SuccessResponse(
        message="CLI update recorded.", data=_cli_update_response(update), meta=_meta()
    )


# ---- POST /cli/plugins/install, POST /cli/plugins/remove ------------------------------------


@router.post(
    "/cli/plugins/install",
    response_model=SuccessResponse[CliPluginResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Install a CLI plugin",
    dependencies=[Depends(require_administrator)],
)
async def install_plugin(
    organization_id: OrganizationId,
    repos: Repos,
    plugin_service: CliPluginServiceDep,
    body: PluginInstallRequest,
    actor: CurrentUserId,
) -> SuccessResponse[CliPluginResponse]:
    plugin = await repos.cli_plugins.find_by_name(organization_id, name=body.name)
    if plugin is None:
        plugin = await plugin_service.register(
            organization_id,
            name=body.name,
            version=body.version,
            checksum_sha256=body.checksum_sha256,
            is_signed=body.is_signed,
            marketplace_ref=body.marketplace_ref,
        )
    current_status = PluginStatus(plugin.status)
    if current_status not in _INSTALL_SOURCE_STATUSES:
        raise ConflictError(
            f"Plugin {body.name!r} cannot be installed from its current status "
            f"{current_status.value!r}."
        )
    try:
        plugin = await plugin_service.transition(
            plugin, target=PluginStatus.INSTALLED, actor_id=actor, now=datetime.now(UTC)
        )
    except PluginTransitionRefusedError as exc:
        raise ConflictError(
            f"Plugin {body.name!r} cannot be installed: {exc.result.detail}"
        ) from exc
    return SuccessResponse(
        message="Plugin installed.", data=_cli_plugin_response(plugin), meta=_meta()
    )


@router.post(
    "/cli/plugins/remove",
    response_model=SuccessResponse[CliPluginResponse],
    summary="Remove a CLI plugin",
    dependencies=[Depends(require_administrator)],
)
async def remove_plugin(
    organization_id: OrganizationId,
    repos: Repos,
    plugin_service: CliPluginServiceDep,
    body: PluginRemoveRequest,
    actor: CurrentUserId,
) -> SuccessResponse[CliPluginResponse]:
    plugin = await repos.cli_plugins.find_by_name(organization_id, name=body.name)
    if plugin is None:
        raise ConflictError(f"Plugin {body.name!r} was not found in this organization.")
    try:
        plugin = await plugin_service.transition(
            plugin, target=PluginStatus.REMOVED, actor_id=actor, now=datetime.now(UTC)
        )
    except PluginTransitionRefusedError as exc:
        raise ConflictError(f"Plugin {body.name!r} cannot be removed: {exc.result.detail}") from exc
    return SuccessResponse(
        message="Plugin removed.", data=_cli_plugin_response(plugin), meta=_meta()
    )


# ---- GET /cli/statistics, GET /sdk/statistics, GET /sdk/reports ------------------------------


@router.get(
    "/cli/statistics", response_model=SuccessResponse[StatisticsResponse], summary="CLI statistics"
)
async def get_cli_statistics(
    organization_id: OrganizationId, repos: Repos, since: datetime | None = None
) -> SuccessResponse[StatisticsResponse]:
    window_since = since or _default_window(7)[0]
    rows = await repos.statistics.list_range(organization_id, since=window_since)
    data = StatisticsResponse(
        windows=[
            StatisticWindowResponse(
                window_start=row.window_start,
                window_end=row.window_end,
                sdk_download_count=row.sdk_download_count,
                cli_download_count=row.cli_download_count,
                command_execution_count=row.command_execution_count,
                plugin_install_count=row.plugin_install_count,
                auth_success_count=row.auth_success_count,
                auth_failure_count=row.auth_failure_count,
            )
            for row in rows
        ],
        total=len(rows),
    )
    return SuccessResponse(message="CLI statistics retrieved.", data=data, meta=_meta())


@router.get(
    "/sdk/statistics", response_model=SuccessResponse[StatisticsResponse], summary="SDK statistics"
)
async def get_sdk_statistics(
    organization_id: OrganizationId, repos: Repos, since: datetime | None = None
) -> SuccessResponse[StatisticsResponse]:
    window_since = since or _default_window(7)[0]
    rows = await repos.statistics.list_range(organization_id, since=window_since)
    data = StatisticsResponse(
        windows=[
            StatisticWindowResponse(
                window_start=row.window_start,
                window_end=row.window_end,
                sdk_download_count=row.sdk_download_count,
                cli_download_count=row.cli_download_count,
                command_execution_count=row.command_execution_count,
                plugin_install_count=row.plugin_install_count,
                auth_success_count=row.auth_success_count,
                auth_failure_count=row.auth_failure_count,
            )
            for row in rows
        ],
        total=len(rows),
    )
    return SuccessResponse(message="SDK statistics retrieved.", data=data, meta=_meta())


@router.get(
    "/sdk/reports", response_model=SuccessResponse[ReportsResponse], summary="Generated reports"
)
async def get_sdk_reports(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
) -> SuccessResponse[ReportsResponse]:
    rows = await repos.reports.list_recent(organization_id, limit=limit)
    data = ReportsResponse(reports=[_report_response(row) for row in rows], total=len(rows))
    return SuccessResponse(message="Reports retrieved.", data=data, meta=_meta())


__all__ = ["router"]
