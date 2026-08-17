"""Test suites and test cases."""

from __future__ import annotations

from uuid import UUID

from app.models.enums import TestType
from app.models.test_definitions import TestCase, TestSuite
from app.repositories.test_definitions import TestCaseRepository, TestSuiteRepository


class TestSuiteService:
    def __init__(self, repo: TestSuiteRepository) -> None:
        self._repo = repo

    async def create(
        self, organization_id: UUID, *, name: str, test_type: TestType, description: str = ""
    ) -> TestSuite:
        return await self._repo.create(
            TestSuite(
                organization_id=organization_id,
                name=name,
                test_type=test_type,
                description=description,
            )
        )


class TestCaseService:
    def __init__(self, repo: TestCaseRepository) -> None:
        self._repo = repo

    async def create(
        self, organization_id: UUID, *, test_suite_id: UUID, name: str, description: str = ""
    ) -> TestCase:
        return await self._repo.create(
            TestCase(
                organization_id=organization_id,
                test_suite_id=test_suite_id,
                name=name,
                description=description,
            )
        )


__all__ = ["TestCaseService", "TestSuiteService"]
