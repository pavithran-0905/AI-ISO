"""Test environments, reusable test data sets, and mock services."""

from __future__ import annotations

from shared_core.database.base import BaseModel
from sqlalchemy import Boolean, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import MockServiceType, TestEnvironmentType


class TestEnvironment(BaseModel):
    """``test_environments`` -- one named environment tests can run
    against (local, QA, UAT, staging, an ephemeral one, and so on)."""

    __tablename__ = "test_environments"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_test_environment_name"),)

    name: Mapped[str] = mapped_column(String(128), index=True)
    environment_type: Mapped[TestEnvironmentType] = mapped_column(String(32), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class TestDataSet(BaseModel):
    """``test_data_sets`` -- one named, reusable set of test/seed
    data."""

    __tablename__ = "test_data_sets"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_test_data_set_name"),)

    name: Mapped[str] = mapped_column(String(128), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    is_reusable: Mapped[bool] = mapped_column(Boolean, default=True)


class MockService(BaseModel):
    """``mock_services`` -- one mocked external dependency (a REST or
    GraphQL API, a webhook target, a queue, a database, a cloud
    service, a third-party API)."""

    __tablename__ = "mock_services"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_mock_service_name"),)

    name: Mapped[str] = mapped_column(String(128), index=True)
    mock_type: Mapped[MockServiceType] = mapped_column(String(24), index=True)
    target_ref: Mapped[str] = mapped_column(String(512), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


__all__ = ["MockService", "TestDataSet", "TestEnvironment"]
