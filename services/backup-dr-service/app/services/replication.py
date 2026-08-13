"""Replication monitoring: lag classification against configured
thresholds.

Wires ``app.replication.engine``'s pure lag classification onto the
repository that persists replication job status.
"""

from __future__ import annotations

from app.models.recovery import ReplicationJob
from app.replication.engine import assess_lag
from app.repositories.recovery import ReplicationJobRepository


class ReplicationService:
    """Classifies and persists replication health."""

    def __init__(
        self,
        repo: ReplicationJobRepository,
        *,
        warning_threshold_seconds: float,
        critical_threshold_seconds: float,
    ) -> None:
        self._repo = repo
        self._warning_threshold = warning_threshold_seconds
        self._critical_threshold = critical_threshold_seconds

    async def refresh_status(self, job: ReplicationJob) -> ReplicationJob:
        """Recompute *job*'s status from its currently-recorded lag."""
        assessment = assess_lag(
            job.lag_seconds,
            warning_threshold_seconds=self._warning_threshold,
            critical_threshold_seconds=self._critical_threshold,
        )
        job.status = assessment.status
        await self._repo.update(job)
        return job


__all__ = ["ReplicationService"]
