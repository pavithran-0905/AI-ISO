"""The 13 docs/072 REST endpoints.

**Every route derives its tenant from the token.** No query or body
parameter names an organization; see
:func:`app.api.deps.get_organization_id` for why that is not a
convenience.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from shared_core.exceptions.authorization import AuthorizationError
from shared_core.exceptions.conflict import ConflictError
from shared_core.exceptions.not_found import NotFoundError
from shared_core.exceptions.validation import ValidationError
from shared_core.logging.context import get_log_context

from app.api.deps import (
    ConfigurationServiceDep,
    CurrentUserId,
    DeviceServiceDep,
    OrganizationId,
    ProfileServiceDep,
    PushServiceDep,
    QrServiceDep,
    Repos,
    ServiceSettings,
    SessionServiceDep,
    StatisticsServiceDep,
    SyncServiceDep,
    TokenServiceDep,
    require_administrator,
)
from app.models.devices import MobileDevice, MobileProfile
from app.models.enums import MobilePlatform, QrPurpose, ReportKind, ReportStatus
from app.models.notifications import MobileNotification, MobilePushToken
from app.models.reporting import MobileReport
from app.schemas.mobile import (
    MAX_PAGE_SIZE,
    ConfigurationResponse,
    DeviceLoginRequest,
    DeviceRegisterRequest,
    DeviceResponse,
    LoginResponse,
    LogoutRequest,
    LogoutResponse,
    NotificationResponse,
    NotificationsResponse,
    ProfileResponse,
    ProfileUpdateRequest,
    PushRegisterRequest,
    PushTokenResponse,
    QrRegisterRequest,
    ReportResponse,
    ReportsResponse,
    StatisticsResponse,
    SyncRequest,
    SyncResponse,
    VersionPolicyResponse,
)
from app.schemas.response import ResponseMeta, SuccessResponse
from app.services.sessions import LoginRefusedError
from app.services.sync import SyncItemInput
from app.versions.engine import is_below_minimum, is_update_recommended

router = APIRouter(tags=["Mobile"])


def _meta() -> ResponseMeta:
    return ResponseMeta(request_id=get_log_context().request_id or "unknown")


def _device_response(device: MobileDevice) -> DeviceResponse:
    return DeviceResponse(
        id=device.id,
        device_identifier=device.device_identifier,
        platform=device.platform,
        trust_status=str(device.trust_status),
        device_model=device.device_model,
        os_version=device.os_version,
        app_version=device.app_version_label,
        last_seen_at=device.last_seen_at,
    )


def _profile_response(profile: MobileProfile) -> ProfileResponse:
    return ProfileResponse(
        user_id=profile.user_id,
        display_name=profile.display_name,
        locale=profile.locale,
        timezone=profile.timezone,
        preferences=profile.preferences,
    )


def _notification_response(notification: MobileNotification) -> NotificationResponse:
    return NotificationResponse(
        id=notification.id,
        device_id=notification.device_id,
        title=notification.title,
        body=notification.body,
        category=notification.category,
        status=notification.status,
        retry_count=notification.retry_count,
        delivered_at=notification.delivered_at,
        read_at=notification.read_at,
    )


def _push_token_response(token: MobilePushToken) -> PushTokenResponse:
    return PushTokenResponse(
        id=token.id,
        device_id=token.device_id,
        platform=token.platform,
        status=token.status,
        registered_at=token.registered_at,
    )


def _report_response(report: MobileReport) -> ReportResponse:
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


# ---- POST /mobile/login, POST /mobile/logout --------------------------------------------------


@router.post(
    "/mobile/login",
    response_model=SuccessResponse[LoginResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Authenticate a mobile device and establish a session",
)
async def login(
    organization_id: OrganizationId,
    actor: CurrentUserId,
    device_service: DeviceServiceDep,
    session_service: SessionServiceDep,
    token_service: TokenServiceDep,
    settings: ServiceSettings,
    body: DeviceLoginRequest,
) -> SuccessResponse[LoginResponse]:
    now = datetime.now(UTC)
    device, _created = await device_service.find_or_register(
        organization_id,
        device_identifier=body.device_identifier,
        platform=body.platform,
        device_model=body.device_model,
        os_version=body.os_version,
        app_version_label=body.app_version,
        now=now,
        actor_id=actor,
        is_jailbroken=body.is_jailbroken,
        is_rooted=body.is_rooted,
    )
    try:
        session = await session_service.login(
            device,
            user_id=actor,
            auth_method=body.auth_method,
            now=now,
            session_max_age_minutes=settings.session_max_age_minutes,
        )
    except LoginRefusedError as exc:
        raise AuthorizationError(exc.detail) from exc

    _token, raw_token = await token_service.issue(
        organization_id, device_id=device.id, now=now, max_age_days=settings.token_max_age_days
    )
    data = LoginResponse(
        session_id=session.id,
        device_id=device.id,
        user_id=actor,
        auth_method=session.auth_method,
        is_new_device=session.is_new_device,
        issued_at=session.issued_at,
        expires_at=session.expires_at,
        mobile_token=raw_token,
    )
    return SuccessResponse(message="Login successful.", data=data, meta=_meta())


@router.post(
    "/mobile/logout", response_model=SuccessResponse[LogoutResponse], summary="End a mobile session"
)
async def logout(
    organization_id: OrganizationId,
    actor: CurrentUserId,
    repos: Repos,
    session_service: SessionServiceDep,
    body: LogoutRequest,
) -> SuccessResponse[LogoutResponse]:
    device = await repos.devices.find_by_identifier(
        organization_id, device_identifier=body.device_identifier
    )
    if device is None:
        raise NotFoundError(f"Device {body.device_identifier!r} was not found.")
    session = await repos.sessions.find_active_for_device(
        organization_id, device_id=device.id, user_id=actor
    )
    if session is None:
        raise NotFoundError("No active session was found for this device.")
    session = await session_service.logout(session, now=datetime.now(UTC))
    data = LogoutResponse(session_id=session.id, status=str(session.status))
    return SuccessResponse(message="Logout successful.", data=data, meta=_meta())


# ---- POST /mobile/register-device --------------------------------------------------------------


@router.post(
    "/mobile/register-device",
    response_model=SuccessResponse[DeviceResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register a mobile device",
)
async def register_device(
    organization_id: OrganizationId,
    actor: CurrentUserId,
    device_service: DeviceServiceDep,
    body: DeviceRegisterRequest,
) -> SuccessResponse[DeviceResponse]:
    device, _created = await device_service.find_or_register(
        organization_id,
        device_identifier=body.device_identifier,
        platform=body.platform,
        device_model=body.device_model,
        os_version=body.os_version,
        app_version_label=body.app_version,
        now=datetime.now(UTC),
        actor_id=actor,
    )
    return SuccessResponse(
        message="Device registered.", data=_device_response(device), meta=_meta()
    )


# ---- GET/PUT /mobile/profile -----------------------------------------------------------------


@router.get(
    "/mobile/profile",
    response_model=SuccessResponse[ProfileResponse],
    summary="Get the caller's mobile profile",
)
async def get_profile(
    organization_id: OrganizationId, actor: CurrentUserId, profile_service: ProfileServiceDep
) -> SuccessResponse[ProfileResponse]:
    profile = await profile_service.get_or_create(organization_id, user_id=actor)
    return SuccessResponse(
        message="Profile retrieved.", data=_profile_response(profile), meta=_meta()
    )


@router.put(
    "/mobile/profile",
    response_model=SuccessResponse[ProfileResponse],
    summary="Update the caller's mobile profile",
)
async def update_profile(
    organization_id: OrganizationId,
    actor: CurrentUserId,
    profile_service: ProfileServiceDep,
    body: ProfileUpdateRequest,
) -> SuccessResponse[ProfileResponse]:
    profile = await profile_service.get_or_create(organization_id, user_id=actor)
    profile = await profile_service.update(
        profile,
        display_name=body.display_name,
        locale=body.locale,
        timezone=body.timezone,
        preferences=body.preferences,
    )
    return SuccessResponse(
        message="Profile updated.", data=_profile_response(profile), meta=_meta()
    )


# ---- POST /mobile/sync -----------------------------------------------------------------------


@router.post(
    "/mobile/sync",
    response_model=SuccessResponse[SyncResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Enqueue a synchronization job",
)
async def create_sync(
    organization_id: OrganizationId, repos: Repos, sync_service: SyncServiceDep, body: SyncRequest
) -> SuccessResponse[SyncResponse]:
    device = await repos.devices.find_by_identifier(
        organization_id, device_identifier=body.device_identifier
    )
    if device is None:
        raise NotFoundError(f"Device {body.device_identifier!r} was not found.")
    items = [
        SyncItemInput(
            action_type=item.action_type,
            payload=item.payload,
            client_updated_at=item.client_updated_at,
        )
        for item in body.items
    ]
    job = await sync_service.enqueue(
        organization_id, device_id=device.id, sync_type=body.sync_type, items=items
    )
    data = SyncResponse(
        sync_job_id=job.id, device_id=device.id, status=job.status, item_count=job.item_count
    )
    return SuccessResponse(message="Synchronization job enqueued.", data=data, meta=_meta())


# ---- GET /mobile/configuration ----------------------------------------------------------------


@router.get(
    "/mobile/configuration",
    response_model=SuccessResponse[ConfigurationResponse],
    summary="Get effective remote configuration",
)
async def get_configuration(
    organization_id: OrganizationId,
    config_service: ConfigurationServiceDep,
    platform: MobilePlatform,
    environment: str = "production",
) -> SuccessResponse[ConfigurationResponse]:
    entries = await config_service.resolve(
        organization_id, platform=platform, environment=environment
    )
    data = ConfigurationResponse(environment=environment, platform=platform, entries=entries)
    return SuccessResponse(message="Configuration resolved.", data=data, meta=_meta())


# ---- GET /mobile/notifications --------------------------------------------------------------


@router.get(
    "/mobile/notifications",
    response_model=SuccessResponse[NotificationsResponse],
    summary="List a device's push notifications",
)
async def list_notifications(
    organization_id: OrganizationId,
    repos: Repos,
    device_identifier: str,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
) -> SuccessResponse[NotificationsResponse]:
    device = await repos.devices.find_by_identifier(
        organization_id, device_identifier=device_identifier
    )
    if device is None:
        raise NotFoundError(f"Device {device_identifier!r} was not found.")
    rows = await repos.notifications.list_for_device(
        organization_id, device_id=device.id, limit=limit
    )
    data = NotificationsResponse(
        notifications=[_notification_response(row) for row in rows], total=len(rows)
    )
    return SuccessResponse(message="Notifications retrieved.", data=data, meta=_meta())


# ---- POST /mobile/push/register --------------------------------------------------------------


@router.post(
    "/mobile/push/register",
    response_model=SuccessResponse[PushTokenResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register a device's push token",
)
async def register_push_token(
    organization_id: OrganizationId,
    repos: Repos,
    push_service: PushServiceDep,
    body: PushRegisterRequest,
) -> SuccessResponse[PushTokenResponse]:
    device = await repos.devices.find_by_identifier(
        organization_id, device_identifier=body.device_identifier
    )
    if device is None:
        raise NotFoundError(f"Device {body.device_identifier!r} was not found.")
    token = await push_service.register_token(
        organization_id,
        device_id=device.id,
        platform=body.platform,
        token_value=body.token_value,
        now=datetime.now(UTC),
    )
    return SuccessResponse(
        message="Push token registered.", data=_push_token_response(token), meta=_meta()
    )


# ---- POST /mobile/qr/register ------------------------------------------------------------------


@router.post(
    "/mobile/qr/register",
    response_model=SuccessResponse[DeviceResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Complete device enrollment via a QR onboarding token",
)
async def register_via_qr(
    organization_id: OrganizationId,
    actor: CurrentUserId,
    device_service: DeviceServiceDep,
    qr_service: QrServiceDep,
    body: QrRegisterRequest,
) -> SuccessResponse[DeviceResponse]:
    payload = await qr_service.redeem(body.qr_token)
    if payload is None:
        raise ConflictError("This QR code is invalid, already used, or has expired.")
    if payload.get("purpose") != QrPurpose.DEVICE_ENROLLMENT.value:
        raise ConflictError("This QR code was not issued for device enrollment.")
    if payload.get("organization_id") != str(organization_id):
        raise AuthorizationError("This QR code was not issued for your organization.")

    device, _created = await device_service.find_or_register(
        organization_id,
        device_identifier=body.device_identifier,
        platform=body.platform,
        device_model=body.device_model,
        os_version=body.os_version,
        app_version_label=body.app_version,
        now=datetime.now(UTC),
        actor_id=actor,
    )
    return SuccessResponse(
        message="Device enrolled via QR code.", data=_device_response(device), meta=_meta()
    )


# ---- GET /mobile/version ------------------------------------------------------------------------


@router.get(
    "/mobile/version",
    response_model=SuccessResponse[VersionPolicyResponse],
    summary="Get the current app version policy",
)
async def get_version_policy(
    organization_id: OrganizationId, repos: Repos, platform: MobilePlatform, current_version: str
) -> SuccessResponse[VersionPolicyResponse]:
    policy = await repos.app_versions.find_latest_for_platform(organization_id, platform=platform)
    if policy is None:
        raise NotFoundError(
            f"No version policy has been published for platform {platform.value!r}."
        )
    try:
        below_minimum = is_below_minimum(current_version, policy.minimum_version_label)
        update_recommended = is_update_recommended(
            current_version, policy.recommended_version_label
        )
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc

    data = VersionPolicyResponse(
        platform=platform,
        latest_version=policy.version_label,
        minimum_version=policy.minimum_version_label,
        recommended_version=policy.recommended_version_label,
        is_below_minimum=below_minimum,
        is_update_recommended=update_recommended,
        is_forced_upgrade=policy.is_forced_upgrade,
        release_notes=policy.release_notes,
        released_at=policy.released_at,
    )
    return SuccessResponse(message="Version policy retrieved.", data=data, meta=_meta())


# ---- GET /mobile/statistics, GET /mobile/reports ------------------------------------------------


@router.get(
    "/mobile/statistics",
    response_model=SuccessResponse[StatisticsResponse],
    summary="Fleet-wide mobile statistics",
    dependencies=[Depends(require_administrator)],
)
async def get_statistics(
    organization_id: OrganizationId,
    stats_service: StatisticsServiceDep,
    since: datetime | None = None,
    until: datetime | None = None,
) -> SuccessResponse[StatisticsResponse]:
    window_until = until or datetime.now(UTC)
    window_since = since or (window_until - timedelta(days=7))
    snapshot = await stats_service.compute(organization_id, since=window_since, until=window_until)
    data = StatisticsResponse(
        window_start=snapshot.window_start,
        window_end=snapshot.window_end,
        daily_active_users=snapshot.daily_active_users,
        session_count=snapshot.session_count,
        average_session_duration_seconds=snapshot.average_session_duration_seconds,
        crash_count=snapshot.crash_count,
        crash_rate=snapshot.crash_rate,
        offline_usage_ratio=snapshot.offline_usage_ratio,
        notification_engagement_rate=snapshot.notification_engagement_rate,
        sync_success_rate=snapshot.sync_success_rate,
    )
    return SuccessResponse(message="Statistics computed.", data=data, meta=_meta())


@router.get(
    "/mobile/reports",
    response_model=SuccessResponse[ReportsResponse],
    summary="Generated mobile reports",
    dependencies=[Depends(require_administrator)],
)
async def get_reports(
    organization_id: OrganizationId,
    repos: Repos,
    kind: ReportKind | None = None,
    report_status: ReportStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
) -> SuccessResponse[ReportsResponse]:
    rows = await repos.reports.list_recent(
        organization_id, kind=kind, status=report_status, limit=limit
    )
    data = ReportsResponse(reports=[_report_response(row) for row in rows], total=len(rows))
    return SuccessResponse(message="Reports retrieved.", data=data, meta=_meta())


__all__ = ["router"]
