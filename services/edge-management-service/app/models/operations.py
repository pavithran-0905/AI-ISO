"""Ongoing operational state per device: configuration, synchronization,
updates, firmware catalog, applications, AI models, protocol
connectivity, and component health.

**Every table here is a time series of readings or executions, never a
single mutable row a fresh check overwrites in place** -- matching
``services/multi-cluster-management-service``'s own operations tables.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import (
    AiModelStatus,
    ApplicationDeploymentStrategy,
    ApplicationStatus,
    ComponentHealthStatus,
    ConflictResolutionStrategy,
    DeviceComponent,
    EdgeDeviceType,
    InferenceTarget,
    ProtocolHealthStatus,
    ProtocolKind,
    SyncKind,
    SyncStatus,
    UpdateKind,
    UpdateStatus,
    UpdateStrategy,
)


class EdgeConfiguration(BaseModel):
    """``edge_configurations`` -- one versioned configuration key/value
    applied to one device. A new value is a new row, never an in-place
    edit of the previous one -- rolling a device's configuration back
    means selecting an earlier row, not reconstructing lost history."""

    __tablename__ = "edge_configurations"
    __table_args__ = (
        Index("ix_edge_configuration_device", "device_id"),
        Index("ix_edge_configuration_key", "config_key"),
    )

    device_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("edge_devices.id", ondelete="CASCADE"), index=True
    )
    config_key: Mapped[str] = mapped_column(String(128), index=True)
    config_value: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    """The configuration's own revision number -- deliberately not named
    ``version``, which :class:`~shared_core.database.base.VersionMixin`
    already reserves as the optimistic-locking counter every
    ``BaseRepository.update()`` call increments; the two would silently
    collide (both ``int``, so nothing but this comment would have
    flagged it) if a config revision were ever bumped by anything other
    than an explicit new row."""
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    """Whether this is the revision currently applied to the device --
    deliberately not named ``is_active``, which
    :class:`~shared_core.database.base.SoftDeleteMixin` already reserves
    as the soft-delete flag every repository's ``_base_select()``
    filters on: setting a domain-named ``is_active`` to ``False`` here
    would silently soft-delete the row out of every future query rather
    than just marking it superseded."""
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class EdgeSynchronization(BaseModel):
    """``edge_synchronization`` -- one sync execution between a device
    and the central platform."""

    __tablename__ = "edge_synchronization"
    __table_args__ = (
        Index("ix_edge_sync_device", "device_id"),
        Index("ix_edge_sync_status", "status"),
    )

    device_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("edge_devices.id", ondelete="CASCADE"), index=True
    )
    sync_kind: Mapped[SyncKind] = mapped_column(String(16))
    status: Mapped[SyncStatus] = mapped_column(String(16), default=SyncStatus.PENDING, index=True)
    conflict_resolution: Mapped[ConflictResolutionStrategy | None] = mapped_column(
        String(16), default=None
    )

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    duration_ms: Mapped[float | None] = mapped_column(Float, default=None)
    bytes_transferred: Mapped[int | None] = mapped_column(BigInteger, default=None)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)


class EdgeUpdate(BaseModel):
    """``edge_updates`` -- one OTA update execution (software, firmware,
    container, or security patch) for one device."""

    __tablename__ = "edge_updates"
    __table_args__ = (
        Index("ix_edge_update_device", "device_id"),
        Index("ix_edge_update_status", "status"),
    )

    device_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("edge_devices.id", ondelete="CASCADE"), index=True
    )
    update_kind: Mapped[UpdateKind] = mapped_column(String(16))
    strategy: Mapped[UpdateStrategy] = mapped_column(String(16), default=UpdateStrategy.STAGED)
    from_version: Mapped[str] = mapped_column(String(32))
    to_version: Mapped[str] = mapped_column(String(32))
    status: Mapped[UpdateStatus] = mapped_column(
        String(16), default=UpdateStatus.PLANNED, index=True
    )

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    duration_ms: Mapped[float | None] = mapped_column(Float, default=None)
    verification_passed: Mapped[bool | None] = mapped_column(Boolean, default=None)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)


class EdgeFirmware(BaseModel):
    """``edge_firmware`` -- the firmware/version catalog upgrade
    planning and compatibility checks are validated against, per device
    type."""

    __tablename__ = "edge_firmware"
    __table_args__ = (Index("ix_edge_firmware_device_type", "device_type"),)

    device_type: Mapped[EdgeDeviceType] = mapped_column(String(32), index=True)
    version_label: Mapped[str] = mapped_column(String(32))
    is_supported: Mapped[bool] = mapped_column(Boolean, default=True)
    is_deprecated: Mapped[bool] = mapped_column(Boolean, default=False)
    release_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    end_of_life_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    skew_rank: Mapped[int] = mapped_column(Integer, default=0)


class EdgeApplication(BaseModel):
    """``edge_applications`` -- one application/container deployment on
    one device."""

    __tablename__ = "edge_applications"
    __table_args__ = (
        Index("ix_edge_application_device", "device_id"),
        Index("ix_edge_application_status", "status"),
    )

    device_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("edge_devices.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    version_label: Mapped[str] = mapped_column(String(32))
    deployment_strategy: Mapped[ApplicationDeploymentStrategy] = mapped_column(
        String(16), default=ApplicationDeploymentStrategy.ROLLING
    )
    status: Mapped[ApplicationStatus] = mapped_column(
        String(16), default=ApplicationStatus.PENDING, index=True
    )
    deployed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class EdgeAiModel(BaseModel):
    """``edge_ai_models`` -- one AI model deployment on one device, with
    the deployment it superseded (if any) for rollback tracking."""

    __tablename__ = "edge_ai_models"
    __table_args__ = (
        Index("ix_edge_ai_model_device", "device_id"),
        Index("ix_edge_ai_model_status", "status"),
    )

    device_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("edge_devices.id", ondelete="CASCADE"), index=True
    )
    rollback_of_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("edge_ai_models.id", ondelete="SET NULL"), default=None
    )
    name: Mapped[str] = mapped_column(String(255))
    version_label: Mapped[str] = mapped_column(String(32))
    status: Mapped[AiModelStatus] = mapped_column(
        String(16), default=AiModelStatus.STAGED, index=True
    )
    inference_target: Mapped[InferenceTarget] = mapped_column(
        String(8), default=InferenceTarget.CPU
    )
    deployed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class EdgeProtocol(BaseModel):
    """``edge_protocols`` -- one industrial protocol endpoint's
    connectivity state for one device. Connectivity is tracked, never
    driven -- this build holds no protocol drivers (see this package's
    README "Scope boundary")."""

    __tablename__ = "edge_protocols"
    __table_args__ = (
        Index("ix_edge_protocol_device", "device_id"),
        Index("ix_edge_protocol_kind", "protocol_kind"),
    )

    device_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("edge_devices.id", ondelete="CASCADE"), index=True
    )
    protocol_kind: Mapped[ProtocolKind] = mapped_column(String(16), index=True)
    status: Mapped[ProtocolHealthStatus] = mapped_column(
        String(16), default=ProtocolHealthStatus.UNKNOWN
    )
    endpoint: Mapped[str | None] = mapped_column(String(512), default=None)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)


class EdgeHealth(BaseModel):
    """``edge_health`` -- one component's health reading at one instant.
    ``app.devices.engine`` rolls a device's most recent reading per
    component up into its overall :class:`~app.models.enums.DeviceHealthStatus`."""

    __tablename__ = "edge_health"
    __table_args__ = (
        Index("ix_edge_health_device", "device_id"),
        Index("ix_edge_health_component", "component"),
        Index("ix_edge_health_checked_at", "checked_at"),
    )

    device_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("edge_devices.id", ondelete="CASCADE"), index=True
    )
    component: Mapped[DeviceComponent] = mapped_column(String(16), index=True)
    status: Mapped[ComponentHealthStatus] = mapped_column(
        String(16), default=ComponentHealthStatus.UNKNOWN
    )
    reading_value: Mapped[float | None] = mapped_column(Float, default=None)
    """A raw numeric reading where one applies (e.g. a temperature in
    Celsius) -- ``None`` for components a single number cannot
    summarize."""
    detail: Mapped[str | None] = mapped_column(Text, default=None)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


__all__ = [
    "EdgeAiModel",
    "EdgeApplication",
    "EdgeConfiguration",
    "EdgeFirmware",
    "EdgeHealth",
    "EdgeProtocol",
    "EdgeSynchronization",
    "EdgeUpdate",
]
