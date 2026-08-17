"""The 12 docs/080 REST endpoints.

**Every route requires an administrator role** -- see
``app.api.deps``'s own module docstring for why.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from shared_core.exceptions.validation import ValidationError
from shared_core.logging.context import get_log_context

from app.api.deps import (
    OrganizationId,
    ReleasePromotionServiceDep,
    ReleaseVersionServiceDep,
    Repos,
    require_administrator,
)
from app.models.channels import ReleaseChannelConfig
from app.models.downloads import DownloadStatistic
from app.models.lifecycle import EolSchedule, LtsVersion
from app.models.packages import ReleaseArtifact
from app.models.promotions import ReleasePromotion
from app.models.releases import ReleaseVersion
from app.models.reporting import ReleaseReport
from app.schemas.releases import (
    MAX_PAGE_SIZE,
    DownloadStatisticResponse,
    DownloadStatisticsResponse,
    EolScheduleResponse,
    EolSchedulesResponse,
    LtsVersionResponse,
    LtsVersionsResponse,
    ReleaseArtifactResponse,
    ReleaseArtifactsResponse,
    ReleaseChannelResponse,
    ReleaseChannelsResponse,
    ReleasePromotionRequest,
    ReleasePromotionResponse,
    ReleasePublishRequest,
    ReleaseReportResponse,
    ReleaseReportsResponse,
    ReleaseStatisticsResponse,
    ReleaseStatisticWindowResponse,
    ReleaseVersionRequest,
    ReleaseVersionResponse,
    ReleaseVersionsResponse,
)
from app.schemas.response import ResponseMeta, SuccessResponse
from app.services.statistics import StatisticsService

router = APIRouter(tags=["Release & Distribution"], dependencies=[Depends(require_administrator)])


def _meta() -> ResponseMeta:
    return ResponseMeta(request_id=get_log_context().request_id or "unknown")


def _version_response(version: ReleaseVersion) -> ReleaseVersionResponse:
    return ReleaseVersionResponse(
        id=version.id,
        version_label=version.version_label,
        release_channel_id=version.release_channel_id,
        status=version.status,
        is_security_release=version.is_security_release,
        released_at=version.released_at,
    )


def _promotion_response(promotion: ReleasePromotion) -> ReleasePromotionResponse:
    return ReleasePromotionResponse(
        id=promotion.id,
        release_version_id=promotion.release_version_id,
        from_channel_type=promotion.from_channel_type,
        to_channel_type=promotion.to_channel_type,
        status=promotion.status,
        promoted_at=promotion.promoted_at,
    )


def _artifact_response(artifact: ReleaseArtifact) -> ReleaseArtifactResponse:
    return ReleaseArtifactResponse(
        id=artifact.id,
        release_package_id=artifact.release_package_id,
        artifact_name=artifact.artifact_name,
        storage_uri=artifact.storage_uri,
        checksum_sha256=artifact.checksum_sha256,
        is_signed=artifact.is_signed,
    )


def _download_response(download: DownloadStatistic) -> DownloadStatisticResponse:
    return DownloadStatisticResponse(
        id=download.id,
        release_artifact_id=download.release_artifact_id,
        region_code=download.region_code,
        bytes_transferred=download.bytes_transferred,
        downloaded_at=download.downloaded_at,
    )


def _channel_response(channel: ReleaseChannelConfig) -> ReleaseChannelResponse:
    return ReleaseChannelResponse(
        id=channel.id,
        name=channel.name,
        channel_type=channel.channel_type,
        is_enabled=channel.is_enabled,
    )


def _lts_response(lts_version: LtsVersion) -> LtsVersionResponse:
    return LtsVersionResponse(
        id=lts_version.id,
        release_version_id=lts_version.release_version_id,
        support_ends_at=lts_version.support_ends_at,
        is_active=lts_version.is_active,
    )


def _eol_response(schedule: EolSchedule) -> EolScheduleResponse:
    return EolScheduleResponse(
        id=schedule.id,
        release_version_id=schedule.release_version_id,
        eol_date=schedule.eol_date,
        migration_recommendation=schedule.migration_recommendation,
    )


def _report_response(report: ReleaseReport) -> ReleaseReportResponse:
    return ReleaseReportResponse(
        id=report.id,
        kind=report.kind,
        report_format=str(report.report_format),
        title=report.title,
        status=str(report.status),
        period_start=report.period_start,
        period_end=report.period_end,
        generated_at=report.generated_at,
        row_count=report.row_count,
    )


async def _require_channel(repos: Repos, channel_id: UUID) -> ReleaseChannelConfig:
    return await repos.release_channels.require_by_id(channel_id)


# ---- GET /releases ----------------------------------------------------------------------


@router.get(
    "/releases",
    response_model=SuccessResponse[ReleaseVersionsResponse],
    summary="List release versions",
)
async def list_releases(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[ReleaseVersionsResponse]:
    rows = await repos.release_versions.list_all(organization_id, limit=limit)
    data = ReleaseVersionsResponse(
        releases=[_version_response(row) for row in rows], total=len(rows)
    )
    return SuccessResponse(message="Release versions retrieved.", data=data, meta=_meta())


# ---- POST /releases ---------------------------------------------------------------------


@router.post(
    "/releases",
    response_model=SuccessResponse[ReleaseVersionResponse],
    summary="Create a release version",
)
async def create_release(
    organization_id: OrganizationId,
    service: ReleaseVersionServiceDep,
    repos: Repos,
    body: ReleaseVersionRequest,
) -> SuccessResponse[ReleaseVersionResponse]:
    channel = await _require_channel(repos, body.release_channel_id)
    version = await service.create(
        organization_id,
        version_label=body.version_label,
        release_channel_id=body.release_channel_id,
        channel_type=channel.channel_type,
        is_security_release=body.is_security_release,
    )
    return SuccessResponse(
        message="Release version created.", data=_version_response(version), meta=_meta()
    )


# ---- GET /releases/{id} -----------------------------------------------------------------


@router.get(
    "/releases/{release_version_id}",
    response_model=SuccessResponse[ReleaseVersionResponse],
    summary="Get a release version by id",
)
async def get_release(
    release_version_id: UUID, repos: Repos
) -> SuccessResponse[ReleaseVersionResponse]:
    version = await repos.release_versions.require_by_id(release_version_id)
    return SuccessResponse(
        message="Release version retrieved.", data=_version_response(version), meta=_meta()
    )


# ---- POST /releases/promote -------------------------------------------------------------


@router.post(
    "/releases/promote",
    response_model=SuccessResponse[ReleasePromotionResponse],
    summary="Promote a release version",
)
async def promote_release(
    organization_id: OrganizationId,
    service: ReleasePromotionServiceDep,
    repos: Repos,
    body: ReleasePromotionRequest,
) -> SuccessResponse[ReleasePromotionResponse]:
    version = await repos.release_versions.require_by_id(body.release_version_id)
    channel = await _require_channel(repos, version.release_channel_id)
    promotion = await service.promote(
        organization_id,
        release_version_id=version.id,
        version_label=version.version_label,
        from_channel_type=channel.channel_type,
        to_channel_type=body.to_channel_type,
        approved_by=body.approved_by,
        now=datetime.now(UTC),
    )
    if promotion.status == "completed":
        target_channel = await repos.release_channels.find_by_type(
            organization_id, channel_type=body.to_channel_type
        )
        if target_channel is not None:
            version.release_channel_id = target_channel.id
            await repos.release_versions.update(version)
    return SuccessResponse(
        message="Release promotion evaluated.", data=_promotion_response(promotion), meta=_meta()
    )


# ---- POST /releases/publish -------------------------------------------------------------


@router.post(
    "/releases/publish",
    response_model=SuccessResponse[ReleaseVersionResponse],
    summary="Publish a release version",
)
async def publish_release(
    service: ReleaseVersionServiceDep, repos: Repos, body: ReleasePublishRequest
) -> SuccessResponse[ReleaseVersionResponse]:
    version = await repos.release_versions.require_by_id(body.release_version_id)
    channel = await _require_channel(repos, version.release_channel_id)
    try:
        version = await service.publish(
            version, channel_type=channel.channel_type, now=datetime.now(UTC)
        )
    except Exception as exc:
        raise ValidationError(str(exc)) from exc
    return SuccessResponse(
        message="Release version published.", data=_version_response(version), meta=_meta()
    )


# ---- GET /artifacts ---------------------------------------------------------------------


@router.get(
    "/artifacts",
    response_model=SuccessResponse[ReleaseArtifactsResponse],
    summary="List release artifacts",
)
async def list_artifacts(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[ReleaseArtifactsResponse]:
    rows = await repos.release_artifacts.list_all(organization_id, limit=limit)
    data = ReleaseArtifactsResponse(
        artifacts=[_artifact_response(row) for row in rows], total=len(rows)
    )
    return SuccessResponse(message="Release artifacts retrieved.", data=data, meta=_meta())


# ---- GET /downloads ---------------------------------------------------------------------


@router.get(
    "/downloads",
    response_model=SuccessResponse[DownloadStatisticsResponse],
    summary="List recent downloads",
)
async def list_downloads(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[DownloadStatisticsResponse]:
    rows = await repos.download_statistics.list_recent(organization_id, limit=limit)
    data = DownloadStatisticsResponse(
        downloads=[_download_response(row) for row in rows], total=len(rows)
    )
    return SuccessResponse(message="Downloads retrieved.", data=data, meta=_meta())


# ---- GET /channels ----------------------------------------------------------------------


@router.get(
    "/channels",
    response_model=SuccessResponse[ReleaseChannelsResponse],
    summary="List release channels",
)
async def list_channels(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[ReleaseChannelsResponse]:
    rows = await repos.release_channels.list_all(organization_id, limit=limit)
    data = ReleaseChannelsResponse(
        channels=[_channel_response(row) for row in rows], total=len(rows)
    )
    return SuccessResponse(message="Release channels retrieved.", data=data, meta=_meta())


# ---- GET /lts ---------------------------------------------------------------------------


@router.get(
    "/lts", response_model=SuccessResponse[LtsVersionsResponse], summary="List LTS versions"
)
async def list_lts(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[LtsVersionsResponse]:
    rows = await repos.lts_versions.list_all(organization_id, limit=limit)
    data = LtsVersionsResponse(lts_versions=[_lts_response(row) for row in rows], total=len(rows))
    return SuccessResponse(message="LTS versions retrieved.", data=data, meta=_meta())


# ---- GET /eol ---------------------------------------------------------------------------


@router.get(
    "/eol",
    response_model=SuccessResponse[EolSchedulesResponse],
    summary="List end-of-life schedules",
)
async def list_eol(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[EolSchedulesResponse]:
    rows = await repos.eol_schedule.list_all(organization_id, limit=limit)
    data = EolSchedulesResponse(schedules=[_eol_response(row) for row in rows], total=len(rows))
    return SuccessResponse(message="End-of-life schedules retrieved.", data=data, meta=_meta())


# ---- GET /reports -----------------------------------------------------------------------


@router.get(
    "/reports",
    response_model=SuccessResponse[ReleaseReportsResponse],
    summary="Generated release reports",
)
async def list_reports(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
) -> SuccessResponse[ReleaseReportsResponse]:
    rows = await repos.reports.list_recent(organization_id, limit=limit)
    data = ReleaseReportsResponse(reports=[_report_response(row) for row in rows], total=len(rows))
    return SuccessResponse(message="Reports retrieved.", data=data, meta=_meta())


# ---- GET /statistics --------------------------------------------------------------------


@router.get(
    "/statistics",
    response_model=SuccessResponse[ReleaseStatisticsResponse],
    summary="Release activity statistics",
)
async def statistics(
    organization_id: OrganizationId, repos: Repos, since: datetime | None = None
) -> SuccessResponse[ReleaseStatisticsResponse]:
    service = StatisticsService(repos.statistics)
    window_since = since or (datetime.now(UTC) - timedelta(days=7))
    rows = await service.list_range(organization_id, since=window_since)
    data = ReleaseStatisticsResponse(
        windows=[
            ReleaseStatisticWindowResponse(
                window_start=row.window_start,
                window_end=row.window_end,
                release_count=row.release_count,
                promotion_count=row.promotion_count,
                download_count=row.download_count,
                avg_release_success_rate=row.avg_release_success_rate,
            )
            for row in rows
        ],
        total=len(rows),
    )
    return SuccessResponse(message="Statistics retrieved.", data=data, meta=_meta())


__all__ = ["router"]
