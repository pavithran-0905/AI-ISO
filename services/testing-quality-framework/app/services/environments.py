"""Test environments, test data sets, and mock services."""

from __future__ import annotations

from uuid import UUID

from app.models.enums import MockServiceType, TestEnvironmentType
from app.models.environments import MockService, TestDataSet, TestEnvironment
from app.repositories.environments import (
    MockServiceRepository,
    TestDataSetRepository,
    TestEnvironmentRepository,
)


class TestEnvironmentService:
    def __init__(self, repo: TestEnvironmentRepository) -> None:
        self._repo = repo

    async def create(
        self, organization_id: UUID, *, name: str, environment_type: TestEnvironmentType
    ) -> TestEnvironment:
        return await self._repo.create(
            TestEnvironment(
                organization_id=organization_id, name=name, environment_type=environment_type
            )
        )


class TestDataSetService:
    def __init__(self, repo: TestDataSetRepository) -> None:
        self._repo = repo

    async def create(
        self, organization_id: UUID, *, name: str, description: str = "", is_reusable: bool = True
    ) -> TestDataSet:
        return await self._repo.create(
            TestDataSet(
                organization_id=organization_id,
                name=name,
                description=description,
                is_reusable=is_reusable,
            )
        )


class MockServiceService:
    def __init__(self, repo: MockServiceRepository) -> None:
        self._repo = repo

    async def create(
        self, organization_id: UUID, *, name: str, mock_type: MockServiceType, target_ref: str = ""
    ) -> MockService:
        return await self._repo.create(
            MockService(
                organization_id=organization_id,
                name=name,
                mock_type=mock_type,
                target_ref=target_ref,
            )
        )


__all__ = ["MockServiceService", "TestDataSetService", "TestEnvironmentService"]
