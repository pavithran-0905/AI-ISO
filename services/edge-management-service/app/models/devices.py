"""Edge devices, gateways, clusters, and inventory.

**A device's ``is_online`` is a denormalized cache of its last
synchronization, never trusted as a live signal.** The health sweep
worker is what actually recomputes it from ``last_seen_at`` staleness --
see ``app.devices.engine.is_stale``, the same staleness check
``services/multi-cluster-management-service`` established for clusters.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import DeviceHealthStatus, DeviceLifecycleState, EdgeDeviceType


class EdgeCluster(BaseModel):
    """``edge_clusters`` -- a logical grouping of edge devices/gateways
    at one site, e.g. "all sensors on production line 3". Distinct from
    a Kubernetes cluster (``services/multi-cluster-management-service``'s
    own concern) -- this is a fleet-management grouping only."""

    __tablename__ = "edge_clusters"
    __table_args__ = (Index("ix_edge_cluster_site", "site_id"),)

    site_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("edge_sites.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    labels: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)


class EdgeGateway(BaseModel):
    """``edge_gateways`` -- one gateway other edge devices connect
    through to reach the central platform."""

    __tablename__ = "edge_gateways"
    __table_args__ = (
        Index("ix_edge_gateway_site", "site_id"),
        Index("ix_edge_gateway_lifecycle_state", "lifecycle_state"),
    )

    site_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("edge_sites.id", ondelete="CASCADE"), index=True
    )
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("edge_locations.id", ondelete="SET NULL"), default=None
    )
    name: Mapped[str] = mapped_column(String(255), index=True)
    lifecycle_state: Mapped[DeviceLifecycleState] = mapped_column(
        String(24), default=DeviceLifecycleState.DISCOVERED, index=True
    )
    health_status: Mapped[DeviceHealthStatus] = mapped_column(
        String(16), default=DeviceHealthStatus.UNKNOWN, index=True
    )
    ip_address: Mapped[str | None] = mapped_column(String(64), default=None)
    is_online: Mapped[bool] = mapped_column(Boolean, default=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    labels: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)


class EdgeDevice(BaseModel):
    """``edge_devices`` -- one edge/industrial device, anywhere in its
    lifecycle from discovery to secure wipe."""

    __tablename__ = "edge_devices"
    __table_args__ = (
        Index("ix_edge_device_site", "site_id"),
        Index("ix_edge_device_gateway", "gateway_id"),
        Index("ix_edge_device_type", "device_type"),
        Index("ix_edge_device_lifecycle_state", "lifecycle_state"),
        Index("ix_edge_device_health_status", "health_status"),
    )

    site_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("edge_sites.id", ondelete="CASCADE"), index=True
    )
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("edge_locations.id", ondelete="SET NULL"), default=None
    )
    gateway_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("edge_gateways.id", ondelete="SET NULL"), default=None, index=True
    )
    cluster_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("edge_clusters.id", ondelete="SET NULL"), default=None
    )

    name: Mapped[str] = mapped_column(String(255), index=True)
    device_type: Mapped[EdgeDeviceType] = mapped_column(String(32), index=True)
    lifecycle_state: Mapped[DeviceLifecycleState] = mapped_column(
        String(24), default=DeviceLifecycleState.DISCOVERED, index=True
    )
    health_status: Mapped[DeviceHealthStatus] = mapped_column(
        String(16), default=DeviceHealthStatus.UNKNOWN, index=True
    )

    serial_number: Mapped[str | None] = mapped_column(String(255), default=None)
    mac_address: Mapped[str | None] = mapped_column(String(64), default=None)
    ip_address: Mapped[str | None] = mapped_column(String(64), default=None)
    firmware_version: Mapped[str | None] = mapped_column(String(32), default=None)

    is_online: Mapped[bool] = mapped_column(Boolean, default=False)
    is_schedulable: Mapped[bool] = mapped_column(Boolean, default=True)
    registered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    labels: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    description: Mapped[str | None] = mapped_column(Text, default=None)


class EdgeInventory(BaseModel):
    """``edge_inventory`` -- one resource-kind count snapshot for one
    device (installed applications, network interfaces, ...), collected
    periodically."""

    __tablename__ = "edge_inventory"
    __table_args__ = (
        Index("ix_edge_inventory_device", "device_id"),
        Index("ix_edge_inventory_kind", "resource_kind"),
    )

    device_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("edge_devices.id", ondelete="CASCADE"), index=True
    )
    resource_kind: Mapped[str] = mapped_column(String(64), index=True)
    resource_count: Mapped[int] = mapped_column(Integer, default=0)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    details: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


__all__ = ["EdgeCluster", "EdgeDevice", "EdgeGateway", "EdgeInventory"]
