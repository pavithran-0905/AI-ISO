"""Benchmark suite and profile definitions."""

from __future__ import annotations

from uuid import UUID

from app.models.benchmark_definitions import BenchmarkProfile, BenchmarkSuite
from app.models.enums import BenchmarkType, LoadProfile
from app.repositories.benchmark_definitions import (
    BenchmarkProfileRepository,
    BenchmarkSuiteRepository,
)


class BenchmarkSuiteService:
    def __init__(self, repo: BenchmarkSuiteRepository) -> None:
        self._repo = repo

    async def create(
        self,
        organization_id: UUID,
        *,
        name: str,
        benchmark_type: BenchmarkType,
        description: str = "",
    ) -> BenchmarkSuite:
        return await self._repo.create(
            BenchmarkSuite(
                organization_id=organization_id,
                name=name,
                benchmark_type=benchmark_type,
                description=description,
            )
        )


class BenchmarkProfileService:
    def __init__(self, repo: BenchmarkProfileRepository) -> None:
        self._repo = repo

    async def create(
        self,
        organization_id: UUID,
        *,
        benchmark_suite_id: UUID,
        name: str,
        load_profile: LoadProfile,
        concurrency: int = 1,
        duration_seconds: int = 60,
    ) -> BenchmarkProfile:
        return await self._repo.create(
            BenchmarkProfile(
                organization_id=organization_id,
                benchmark_suite_id=benchmark_suite_id,
                name=name,
                load_profile=load_profile,
                concurrency=concurrency,
                duration_seconds=duration_seconds,
            )
        )


__all__ = ["BenchmarkProfileService", "BenchmarkSuiteService"]
