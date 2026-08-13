"""Snapshot cataloguing: creation, expiration, and quota enforcement.

Wires ``app.snapshots.engine``'s pure expiration and quota logic onto
the repository that persists the catalog.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models.backup import BackupSnapshot
from app.models.enums import SnapshotKind, SnapshotStatus
from app.repositories.backup import BackupSnapshotRepository
from app.snapshots.engine import SnapshotRecord, enforce_quota, expired_snapshots


def _to_record(row: BackupSnapshot) -> SnapshotRecord:
    return SnapshotRecord(
        snapshot_id=str(row.id),
        target_id=str(row.target_id),
        created_at_source=row.created_at_source,
        expires_at=row.expires_at,
        is_validated=row.is_validated,
    )


class SnapshotService:
    """Creates snapshots and applies expiration/quota policy."""

    def __init__(self, repo: BackupSnapshotRepository) -> None:
        self._repo = repo

    async def create_snapshot(
        self,
        organization_id: UUID,
        *,
        target_id: UUID,
        job_id: UUID | None,
        snapshot_kind: SnapshotKind,
        storage_ref: str | None,
        size_bytes: int | None,
        created_at_source: datetime,
        expires_at: datetime | None,
    ) -> BackupSnapshot:
        return await self._repo.create(
            BackupSnapshot(
                organization_id=organization_id,
                target_id=target_id,
                job_id=job_id,
                snapshot_kind=snapshot_kind,
                status=SnapshotStatus.AVAILABLE,
                storage_ref=storage_ref,
                size_bytes=size_bytes,
                created_at_source=created_at_source,
                expires_at=expires_at,
            )
        )

    async def sweep_expired(self, organization_id: UUID, *, now: datetime) -> int:
        """Mark every expired snapshot for one organization, returning
        how many were expired this sweep."""
        rows = await self._repo.list_recent(organization_id, limit=5000)
        records = [_to_record(row) for row in rows]
        expired = expired_snapshots(records, now=now)
        expired_ids = {record.snapshot_id for record in expired}
        count = 0
        for row in rows:
            if str(row.id) in expired_ids and row.status is not SnapshotStatus.EXPIRED:
                row.status = SnapshotStatus.EXPIRED
                await self._repo.update(row)
                count += 1
        return count

    async def enforce_target_quota(
        self, target_id: UUID, rows: list[BackupSnapshot], *, max_per_target: int
    ) -> int:
        """Delete (soft) snapshots beyond *max_per_target* for one target,
        oldest first. Returns how many were evicted."""
        records = [_to_record(row) for row in rows]
        result = enforce_quota(records, max_per_target=max_per_target)
        evicted_ids = {record.snapshot_id for record in result.evicted}
        count = 0
        for row in rows:
            if str(row.id) in evicted_ids:
                await self._repo.delete(row.id)
                count += 1
        return count


__all__ = ["SnapshotService"]
