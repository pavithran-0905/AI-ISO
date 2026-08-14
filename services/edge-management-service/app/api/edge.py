"""The 13 docs/067 REST endpoints (plus one conventional single-device
GET for detail navigation, matching every other AI-IOS service's
pattern of exposing a singular GET alongside PUT/DELETE).

**Every route derives its tenant from the token.** No query or body
parameter names an organization; see
:func:`app.api.deps.get_organization_id` for why that is not a
convenience.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from shared_core.exceptions.conflict import ConflictError
from shared_core.logging.context import get_log_context

from app.api.deps import (
    AuditServiceDep,
    CurrentUserId,
    DeviceServiceDep,
    OrganizationId,
    OTAServiceDep,
    Repos,
    SiteServiceDep,
    SynchronizationServiceDep,
    require_administrator,
)
from app.models.devices import EdgeDevice
from app.models.enums import AuditAction, DeviceLifecycleState
from app.models.sites import EdgeSite
from app.schemas.edge import (
    MAX_PAGE_SIZE,
    DeviceCreateRequest,
    DeviceHealthResponse,
    DeviceResponse,
    DevicesResponse,
    DeviceUpdateRequest,
    FleetHealthResponse,
    PageInfo,
    ProvisionRequest,
    RemoteAccessRequest,
    RemoteAccessResponse,
    ReportResponse,
    ReportsResponse,
    SiteCreateRequest,
    SiteResponse,
    SitesResponse,
    StatisticsResponse,
    StatisticWindowResponse,
    SyncRequest,
    SyncResponse,
    UpdateRequest,
    UpdateResponse,
)
from app.schemas.response import ResponseMeta, SuccessResponse
from app.services.devices import CredentialRefusedError, TransitionRefusedError
from app.services.ota import UpdatePlanRefusedError

router = APIRouter(prefix="/edge", tags=["Edge Management"])


def _meta() -> ResponseMeta:
    return ResponseMeta(request_id=get_log_context().request_id or "unknown")


def _default_window(days: int) -> tuple[datetime, datetime]:
    end = datetime.now(UTC)
    return end - timedelta(days=days), end


def _site_response(site: EdgeSite) -> SiteResponse:
    return SiteResponse(
        id=site.id,
        name=site.name,
        business_unit=site.business_unit,
        description=site.description,
        geo_latitude=site.geo_latitude,
        geo_longitude=site.geo_longitude,
    )


def _device_response(device: EdgeDevice) -> DeviceResponse:
    return DeviceResponse(
        id=device.id,
        site_id=device.site_id,
        gateway_id=device.gateway_id,
        location_id=device.location_id,
        cluster_id=device.cluster_id,
        name=device.name,
        device_type=device.device_type,
        lifecycle_state=device.lifecycle_state,
        health_status=device.health_status,
        serial_number=device.serial_number,
        firmware_version=device.firmware_version,
        is_online=device.is_online,
        is_schedulable=device.is_schedulable,
        registered_at=device.registered_at,
        last_seen_at=device.last_seen_at,
    )


# ---- GET /edge/health, /statistics, /reports -------------------------------------------------


@router.get(
    "/health", response_model=SuccessResponse[FleetHealthResponse], summary="Fleet-wide health"
)
async def fleet_health(
    organization_id: OrganizationId, repos: Repos
) -> SuccessResponse[FleetHealthResponse]:
    devices = await repos.devices.list_recent(organization_id, limit=MAX_PAGE_SIZE)
    data = FleetHealthResponse(
        devices=[
            DeviceHealthResponse(
                device_id=d.id, health_status=d.health_status, is_online=d.is_online
            )
            for d in devices
        ],
        total=len(devices),
    )
    return SuccessResponse(message="Fleet health retrieved.", data=data, meta=_meta())


@router.get(
    "/statistics", response_model=SuccessResponse[StatisticsResponse], summary="Fleet statistics"
)
async def fleet_statistics(
    organization_id: OrganizationId,
    repos: Repos,
    since: datetime | None = None,
) -> SuccessResponse[StatisticsResponse]:
    window_since = since or _default_window(7)[0]
    rows = await repos.statistics.list_range(organization_id, since=window_since)
    data = StatisticsResponse(
        windows=[
            StatisticWindowResponse(
                window_start=row.window_start,
                window_end=row.window_end,
                sites_registered=row.sites_registered,
                devices_online=row.devices_online,
                devices_offline=row.devices_offline,
                synchronizations_completed=row.synchronizations_completed,
                synchronizations_failed=row.synchronizations_failed,
                updates_completed=row.updates_completed,
                updates_failed=row.updates_failed,
            )
            for row in rows
        ],
        total=len(rows),
    )
    return SuccessResponse(message="Fleet statistics retrieved.", data=data, meta=_meta())


@router.get(
    "/reports", response_model=SuccessResponse[ReportsResponse], summary="Generated reports"
)
async def fleet_reports(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
) -> SuccessResponse[ReportsResponse]:
    rows = await repos.reports.list_recent(organization_id, limit=limit)
    data = ReportsResponse(
        reports=[
            ReportResponse(
                id=row.id,
                kind=row.kind,
                report_format=row.report_format,
                title=row.title,
                status=row.status,
                period_start=row.period_start,
                period_end=row.period_end,
                generated_at=row.generated_at,
                row_count=row.row_count,
            )
            for row in rows
        ],
        total=len(rows),
    )
    return SuccessResponse(message="Reports retrieved.", data=data, meta=_meta())


# ---- GET/POST /edge/sites --------------------------------------------------------------------


@router.get("/sites", response_model=SuccessResponse[SitesResponse], summary="List sites")
async def list_sites(
    organization_id: OrganizationId,
    repos: Repos,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[SitesResponse]:
    rows = await repos.sites.list_recent(organization_id, limit=limit)
    data = SitesResponse(
        sites=[_site_response(row) for row in rows], total=len(rows), page=PageInfo()
    )
    return SuccessResponse(message="Sites retrieved.", data=data, meta=_meta())


@router.post(
    "/sites",
    response_model=SuccessResponse[SiteResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register a site",
    dependencies=[Depends(require_administrator)],
)
async def create_site(
    organization_id: OrganizationId,
    site_service: SiteServiceDep,
    body: SiteCreateRequest,
    actor: CurrentUserId,
) -> SuccessResponse[SiteResponse]:
    site = await site_service.register_site(
        organization_id,
        name=body.name,
        business_unit=body.business_unit,
        description=body.description,
        geo_latitude=body.geo_latitude,
        geo_longitude=body.geo_longitude,
        actor_id=actor,
        now=datetime.now(UTC),
    )
    return SuccessResponse(message="Site registered.", data=_site_response(site), meta=_meta())


# ---- GET/POST /edge/devices, GET/PUT/DELETE /edge/devices/{device_id} -------------------------


@router.get("/devices", response_model=SuccessResponse[DevicesResponse], summary="List devices")
async def list_devices(
    organization_id: OrganizationId,
    repos: Repos,
    site_id: UUID | None = None,
    lifecycle_state: DeviceLifecycleState | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[DevicesResponse]:
    rows = await repos.devices.list_recent(
        organization_id, site_id=site_id, lifecycle_state=lifecycle_state, limit=limit
    )
    data = DevicesResponse(
        devices=[_device_response(row) for row in rows], total=len(rows), page=PageInfo()
    )
    return SuccessResponse(message="Devices retrieved.", data=data, meta=_meta())


@router.post(
    "/devices",
    response_model=SuccessResponse[DeviceResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register a device",
    dependencies=[Depends(require_administrator)],
)
async def create_device(
    organization_id: OrganizationId,
    device_service: DeviceServiceDep,
    body: DeviceCreateRequest,
    actor: CurrentUserId,
) -> SuccessResponse[DeviceResponse]:
    try:
        device = await device_service.register_device(
            organization_id,
            site_id=body.site_id,
            name=body.name,
            device_type=body.device_type,
            credential_ref=body.credential_ref,
            credential_expires_at=body.credential_expires_at,
            gateway_id=body.gateway_id,
            location_id=body.location_id,
            serial_number=body.serial_number,
            actor_id=actor,
            now=datetime.now(UTC),
        )
    except CredentialRefusedError as exc:
        raise ConflictError(
            f"Device {body.name!r} cannot be registered: {exc.validation.detail}"
        ) from exc
    return SuccessResponse(
        message="Device registered.", data=_device_response(device), meta=_meta()
    )


@router.get(
    "/devices/{device_id}", response_model=SuccessResponse[DeviceResponse], summary="Get a device"
)
async def get_device(
    organization_id: OrganizationId, repos: Repos, device_id: UUID
) -> SuccessResponse[DeviceResponse]:
    device = await repos.devices.require_in_org(organization_id, device_id)
    return SuccessResponse(message="Device retrieved.", data=_device_response(device), meta=_meta())


@router.put(
    "/devices/{device_id}",
    response_model=SuccessResponse[DeviceResponse],
    summary="Update a device",
    dependencies=[Depends(require_administrator)],
)
async def update_device(
    organization_id: OrganizationId, repos: Repos, device_id: UUID, body: DeviceUpdateRequest
) -> SuccessResponse[DeviceResponse]:
    device = await repos.devices.require_in_org(organization_id, device_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(device, field, value)
    await repos.devices.update(device)
    return SuccessResponse(message="Device updated.", data=_device_response(device), meta=_meta())


@router.delete(
    "/devices/{device_id}",
    response_model=SuccessResponse[DeviceResponse],
    summary="Retire a device",
    dependencies=[Depends(require_administrator)],
)
async def delete_device(
    organization_id: OrganizationId,
    repos: Repos,
    device_service: DeviceServiceDep,
    device_id: UUID,
) -> SuccessResponse[DeviceResponse]:
    device = await repos.devices.require_in_org(organization_id, device_id)
    try:
        device = await device_service.transition_lifecycle(
            device, target=DeviceLifecycleState.RETIRING, now=datetime.now(UTC)
        )
    except TransitionRefusedError as exc:
        raise ConflictError(
            f"Device {device_id!s} cannot be retired right now: {exc.result.detail}"
        ) from exc
    return SuccessResponse(
        message="Device retirement started.", data=_device_response(device), meta=_meta()
    )


# ---- POST /edge/devices/{device_id}/provision, /sync, /update, /remote-access -----------------


@router.post(
    "/devices/{device_id}/provision",
    response_model=SuccessResponse[DeviceResponse],
    summary="Advance a device's lifecycle",
    dependencies=[Depends(require_administrator)],
)
async def provision_device(
    organization_id: OrganizationId,
    repos: Repos,
    device_service: DeviceServiceDep,
    device_id: UUID,
    body: ProvisionRequest,
) -> SuccessResponse[DeviceResponse]:
    device = await repos.devices.require_in_org(organization_id, device_id)
    try:
        device = await device_service.transition_lifecycle(
            device, target=body.target_state, now=datetime.now(UTC)
        )
    except TransitionRefusedError as exc:
        raise ConflictError(
            f"Device {device_id!s} cannot move to {body.target_state.value}: {exc.result.detail}"
        ) from exc
    return SuccessResponse(
        message="Device lifecycle advanced.", data=_device_response(device), meta=_meta()
    )


@router.post(
    "/devices/{device_id}/sync",
    response_model=SuccessResponse[SyncResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Synchronize a device",
)
async def sync_device(
    organization_id: OrganizationId,
    repos: Repos,
    sync_service: SynchronizationServiceDep,
    device_id: UUID,
    body: SyncRequest,
) -> SuccessResponse[SyncResponse]:
    await repos.devices.require_in_org(organization_id, device_id)
    now = datetime.now(UTC)
    sync = await sync_service.start_sync(
        organization_id, device_id=device_id, sync_kind=body.sync_kind, now=now
    )
    sync = await sync_service.complete_sync(sync, bytes_transferred=None, now=datetime.now(UTC))
    data = SyncResponse(
        sync_id=sync.id,
        device_id=device_id,
        sync_kind=sync.sync_kind,
        status=sync.status,
        duration_ms=sync.duration_ms,
    )
    return SuccessResponse(message="Device synchronized.", data=data, meta=_meta())


@router.post(
    "/devices/{device_id}/update",
    response_model=SuccessResponse[UpdateResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Plan an OTA update",
    dependencies=[Depends(require_administrator)],
)
async def update_device_firmware(
    organization_id: OrganizationId,
    repos: Repos,
    ota_service: OTAServiceDep,
    device_id: UUID,
    body: UpdateRequest,
) -> SuccessResponse[UpdateResponse]:
    device = await repos.devices.require_in_org(organization_id, device_id)
    try:
        update = await ota_service.plan_update(
            device, update_kind=body.update_kind, strategy=body.strategy, to_version=body.to_version
        )
    except UpdatePlanRefusedError as exc:
        data = UpdateResponse(
            update_id=None,
            device_id=device_id,
            to_version=body.to_version,
            status=None,
            refusal=exc.validation.refusal,
            detail=exc.validation.detail,
        )
        return SuccessResponse(message="Update was not planned.", data=data, meta=_meta())

    data = UpdateResponse(
        update_id=update.id,
        device_id=device_id,
        to_version=body.to_version,
        status=update.status,
        refusal=None,
        detail="Update planned.",
    )
    return SuccessResponse(message="Update planned.", data=data, meta=_meta())


@router.post(
    "/devices/{device_id}/remote-access",
    response_model=SuccessResponse[RemoteAccessResponse],
    summary="Request remote access to a device",
    dependencies=[Depends(require_administrator)],
)
async def remote_access_device(
    organization_id: OrganizationId,
    repos: Repos,
    audit: AuditServiceDep,
    device_id: UUID,
    body: RemoteAccessRequest,
    actor: CurrentUserId,
) -> SuccessResponse[RemoteAccessResponse]:
    device = await repos.devices.require_in_org(organization_id, device_id)
    granted = device.is_online
    await audit.record(
        organization_id,
        action=AuditAction.REMOTE_ACCESS,
        entity_type="edge_device",
        entity_id=device.id,
        occurred_at=datetime.now(UTC),
        actor_id=actor,
        summary=(
            f"Remote access {'granted' if granted else 'refused'} for device "
            f"{device_id!s}: {body.reason}"
        ),
        succeeded=granted,
    )
    detail = (
        "Device is online; remote access session granted."
        if granted
        else "Device is offline; remote access cannot be granted."
    )
    data = RemoteAccessResponse(device_id=device_id, granted=granted, detail=detail)
    return SuccessResponse(message="Remote access request processed.", data=data, meta=_meta())


__all__ = ["router"]
