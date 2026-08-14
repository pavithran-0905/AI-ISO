"""Enterprise contracts."""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import JSON, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import ApprovalStatus, ContractStatus


class Contract(BaseModel):
    """``contracts`` -- one enterprise contract for a customer."""

    __tablename__ = "contracts"
    __table_args__ = (
        Index("ix_contract_customer", "customer_id"),
        Index("ix_contract_status", "status"),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    status: Mapped[ContractStatus] = mapped_column(
        String(16), default=ContractStatus.DRAFT, index=True
    )
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    terms: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    approval_status: Mapped[ApprovalStatus] = mapped_column(
        String(16), default=ApprovalStatus.PENDING, index=True
    )


__all__ = ["Contract"]
