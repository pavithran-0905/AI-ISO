"""Developer sandbox sessions and mock service definitions."""

from __future__ import annotations

import uuid
from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import MockType, SandboxStatus


class ApiSandboxSession(BaseModel):
    """``api_sandbox`` -- one developer account's isolated sandbox
    session against an API product."""

    __tablename__ = "api_sandbox"
    __table_args__ = (
        Index("ix_api_sandbox_developer", "developer_account_id"),
        Index("ix_api_sandbox_status", "status"),
    )

    developer_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("developer_accounts.id", ondelete="CASCADE"), index=True
    )
    api_product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("api_products.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[SandboxStatus] = mapped_column(
        String(8), default=SandboxStatus.ACTIVE, index=True
    )
    call_count: Mapped[int] = mapped_column(Integer, default=0)
    last_reset_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ApiMockService(BaseModel):
    """``api_mock_services`` -- one configured mock response for an API
    product's sandbox."""

    __tablename__ = "api_mock_services"
    __table_args__ = (Index("ix_api_mock_service_product", "api_product_id"),)

    api_product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("api_products.id", ondelete="CASCADE"), index=True
    )
    endpoint_path: Mapped[str] = mapped_column(String(256))
    mock_type: Mapped[MockType] = mapped_column(String(8), default=MockType.STATIC)
    response_body: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    response_status_code: Mapped[int] = mapped_column(Integer, default=200)
    simulated_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    simulate_error: Mapped[bool] = mapped_column(Boolean, default=False)


__all__ = ["ApiMockService", "ApiSandboxSession"]
