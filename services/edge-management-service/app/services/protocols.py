"""Industrial protocol connectivity tracking.

Wires ``app.protocols.engine``'s pure connectivity classification onto
the repository that persists one endpoint's status per device. Tracks
connectivity state only -- no protocol drivers, per this package's
README "Scope boundary".
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models.enums import ProtocolKind
from app.models.operations import EdgeProtocol
from app.protocols.engine import classify_connectivity
from app.repositories.operations import EdgeProtocolRepository


class ProtocolService:
    def __init__(self, repo: EdgeProtocolRepository) -> None:
        self._repo = repo

    async def register_endpoint(
        self,
        organization_id: UUID,
        *,
        device_id: UUID,
        protocol_kind: ProtocolKind,
        endpoint: str | None,
    ) -> EdgeProtocol:
        return await self._repo.create(
            EdgeProtocol(
                organization_id=organization_id,
                device_id=device_id,
                protocol_kind=protocol_kind,
                endpoint=endpoint,
            )
        )

    async def record_check(
        self,
        protocol: EdgeProtocol,
        *,
        had_error: bool,
        error_message: str | None,
        now: datetime,
        stale_after_minutes: int,
    ) -> EdgeProtocol:
        """Record the outcome of a check performed right now.

        Classifies against *now* itself (not the stale prior
        ``last_checked_at``), since a fresh, error-free check performed
        this instant is unambiguously ``CONNECTED`` -- staleness only
        matters for :mod:`app.workers.protocol_sweep`, which reclassifies
        endpoints nothing has actually re-checked.
        """
        protocol.last_checked_at = now
        protocol.status = classify_connectivity(
            protocol.last_checked_at,
            had_error=had_error,
            now=now,
            stale_after_minutes=stale_after_minutes,
        )
        protocol.error_message = error_message if had_error else None
        return await self._repo.update(protocol)


__all__ = ["ProtocolService"]
