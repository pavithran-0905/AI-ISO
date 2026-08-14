"""Discovered/provisioned cloud resources and their per-category
detail tables.

**A resource's category-specific detail row (compute/storage/network/
database/Kubernetes) is optional and orthogonal to its
``resource_type``** -- the base :class:`CloudResource` row is what every
resource has; a detail row exists only for the categories that need
extra structured fields beyond ``tags``/``labels``.

The column named ``cloud_project_id`` here is deliberately not named
``project_id`` -- ``project_id`` is one of
:class:`~shared_core.database.base.BaseEntityMixin`'s own reserved
columns (AI-IOS's internal project-scoping FK), a wholly different
concept from a cloud provider's own project/resource-group/OU. Reusing
the reserved name would silently shadow it.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import CloudResourceLifecycleState, CloudResourceType


class CloudResource(BaseModel):
    """``cloud_resources`` -- one discovered or provisioned resource,
    anywhere in its lifecycle from discovery to archive."""

    __tablename__ = "cloud_resources"
    __table_args__ = (
        Index("ix_cloud_resource_account", "account_id"),
        Index("ix_cloud_resource_project", "cloud_project_id"),
        Index("ix_cloud_resource_region", "region_id"),
        Index("ix_cloud_resource_type", "resource_type"),
        Index("ix_cloud_resource_lifecycle_state", "lifecycle_state"),
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cloud_accounts.id", ondelete="CASCADE"), index=True
    )
    cloud_project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cloud_projects.id", ondelete="SET NULL"), default=None
    )
    region_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cloud_regions.id", ondelete="SET NULL"), default=None
    )

    resource_type: Mapped[CloudResourceType] = mapped_column(String(24), index=True)
    external_id: Mapped[str] = mapped_column(String(512), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    lifecycle_state: Mapped[CloudResourceLifecycleState] = mapped_column(
        String(16), default=CloudResourceLifecycleState.DISCOVERED, index=True
    )

    tags: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    labels: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)

    discovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    provisioned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class CloudCompute(BaseModel):
    """``cloud_compute`` -- compute-specific attributes for one
    resource (a VM, a container, a function)."""

    __tablename__ = "cloud_compute"
    __table_args__ = (Index("ix_cloud_compute_resource", "resource_id"),)

    resource_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cloud_resources.id", ondelete="CASCADE"), index=True
    )
    instance_type: Mapped[str | None] = mapped_column(String(64), default=None)
    vcpu: Mapped[int | None] = mapped_column(Integer, default=None)
    memory_gb: Mapped[float | None] = mapped_column(Float, default=None)
    is_spot: Mapped[bool] = mapped_column(Boolean, default=False)
    is_reserved: Mapped[bool] = mapped_column(Boolean, default=False)
    is_gpu: Mapped[bool] = mapped_column(Boolean, default=False)
    image_ref: Mapped[str | None] = mapped_column(String(512), default=None)
    utilization_fraction: Mapped[float | None] = mapped_column(Float, default=None)
    """The most recently reported utilization reading, on ``[0, 1]`` --
    supplied by monitoring integration (Prompt 044), never computed by
    this service from a live cloud billing/metrics API. ``None`` means
    nothing has reported a reading yet, and is never treated as idle by
    ``app.finops.engine.is_idle_resource``."""


class CloudStorage(BaseModel):
    """``cloud_storage`` -- storage-specific attributes for one
    resource (a bucket, a block volume, a file share)."""

    __tablename__ = "cloud_storage"
    __table_args__ = (Index("ix_cloud_storage_resource", "resource_id"),)

    resource_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cloud_resources.id", ondelete="CASCADE"), index=True
    )
    storage_class: Mapped[str | None] = mapped_column(String(64), default=None)
    capacity_gb: Mapped[float | None] = mapped_column(Float, default=None)
    is_encrypted: Mapped[bool] = mapped_column(Boolean, default=False)
    is_replicated: Mapped[bool] = mapped_column(Boolean, default=False)


class CloudNetwork(BaseModel):
    """``cloud_networks`` -- network-specific attributes for one
    resource (a VPC, a subnet, a load balancer, a firewall, DNS, VPN)."""

    __tablename__ = "cloud_networks"
    __table_args__ = (Index("ix_cloud_network_resource", "resource_id"),)

    resource_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cloud_resources.id", ondelete="CASCADE"), index=True
    )
    cidr_block: Mapped[str | None] = mapped_column(String(64), default=None)
    gateway_ref: Mapped[str | None] = mapped_column(String(255), default=None)


class CloudDatabase(BaseModel):
    """``cloud_databases`` -- managed-database-specific attributes for
    one resource."""

    __tablename__ = "cloud_databases"
    __table_args__ = (Index("ix_cloud_database_resource", "resource_id"),)

    resource_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cloud_resources.id", ondelete="CASCADE"), index=True
    )
    engine: Mapped[str] = mapped_column(String(32))
    engine_version: Mapped[str | None] = mapped_column(String(32), default=None)
    is_high_availability: Mapped[bool] = mapped_column(Boolean, default=False)
    storage_gb: Mapped[float | None] = mapped_column(Float, default=None)


class CloudKubernetes(BaseModel):
    """``cloud_kubernetes`` -- managed-Kubernetes-specific attributes
    for one resource. ``cluster_reference_id`` is a cross-service
    reference to ``services/multi-cluster-management-service``'s own
    ``Cluster.id`` -- never a foreign key, since that table lives in a
    different service's database entirely (Prompt 066 integration)."""

    __tablename__ = "cloud_kubernetes"
    __table_args__ = (Index("ix_cloud_kubernetes_resource", "resource_id"),)

    resource_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cloud_resources.id", ondelete="CASCADE"), index=True
    )
    cluster_reference_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    node_pool_count: Mapped[int] = mapped_column(Integer, default=0)
    kubernetes_version: Mapped[str | None] = mapped_column(String(32), default=None)
    autoscaling_enabled: Mapped[bool] = mapped_column(Boolean, default=False)


__all__ = [
    "CloudCompute",
    "CloudDatabase",
    "CloudKubernetes",
    "CloudNetwork",
    "CloudResource",
    "CloudStorage",
]
