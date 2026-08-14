"""Edge site and location hierarchy.

**A site is the top-level registered facility; a location is one node in
that site's own physical hierarchy** (building, floor, production line,
cell, zone, rack, room), nested via ``parent_location_id`` so a facility
with an arbitrary depth of physical structure never has to be flattened
to fit a fixed number of levels.
"""

from __future__ import annotations

import uuid

from shared_core.database.base import BaseModel
from sqlalchemy import JSON, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import SiteHierarchyLevel


class EdgeSite(BaseModel):
    """``edge_sites`` -- one registered facility, vehicle, or remote
    installation."""

    __tablename__ = "edge_sites"
    __table_args__ = (Index("ix_edge_site_name", "name"),)

    name: Mapped[str] = mapped_column(String(255), index=True)
    business_unit: Mapped[str | None] = mapped_column(String(255), default=None)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    geo_latitude: Mapped[float | None] = mapped_column(Float, default=None)
    geo_longitude: Mapped[float | None] = mapped_column(Float, default=None)
    labels: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)


class EdgeLocation(BaseModel):
    """``edge_locations`` -- one node in one site's own physical
    hierarchy."""

    __tablename__ = "edge_locations"
    __table_args__ = (
        Index("ix_edge_location_site", "site_id"),
        Index("ix_edge_location_parent", "parent_location_id"),
    )

    site_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("edge_sites.id", ondelete="CASCADE"), index=True
    )
    parent_location_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("edge_locations.id", ondelete="CASCADE"), default=None, index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    hierarchy_level: Mapped[SiteHierarchyLevel] = mapped_column(String(24), index=True)
    labels: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)


__all__ = ["EdgeLocation", "EdgeSite"]
