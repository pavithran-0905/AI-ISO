"""The topology rebuild worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Converts recent spans into ``app.topology.edges.SpanRecord`` and runs
them through ``TopologyService.sweep``, which upserts rather than
replaces -- an edge one sweep does not observe is not deleted, only left
un-refreshed, since :mod:`app.topology.edges`' existence-confidence model
already accounts for silence via staleness rather than presence/absence.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.signals import TraceSpan
from app.services.bundle import build_repositories
from app.services.topology import TopologyService
from app.topology.edges import SpanRecord
from app.topology.enums import SpanKindLabel

logger = get_logger("app.workers.topology_rebuild")

_DEFAULT_ENVIRONMENT = "production"
_NANOS_PER_SECOND = 1_000_000_000
_NANOS_PER_MILLISECOND = 1_000_000


def _to_span_record(row: TraceSpan) -> SpanRecord:
    start_ns = int(row.started_at.timestamp() * _NANOS_PER_SECOND)
    peer = row.attributes.get("peer.service") if isinstance(row.attributes, dict) else None
    return SpanRecord(
        span_id=row.span_id,
        trace_id=row.trace_id,
        parent_span_id=row.parent_span_id,
        service=row.service_name,
        kind=SpanKindLabel(str(row.span_kind)),
        operation=row.name,
        start_ns=start_ns,
        duration_ns=int(row.duration_ms * _NANOS_PER_MILLISECOND),
        errored=str(row.status) == "error",
        peer_service=str(peer) if peer else None,
    )


class TopologyRebuildWorker:
    """Rebuilds the dependency graph from recent spans."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        lookback: timedelta = timedelta(hours=1),
        span_limit: int = 5_000,
    ) -> None:
        self._session_factory = session_factory
        self._lookback = lookback
        self._span_limit = span_limit

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Rebuild every organization's topology from recent spans."""
        now = datetime.now(UTC)
        window_start = now - self._lookback
        window_seconds = self._lookback.total_seconds()
        edges_seen = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)
            topology = TopologyService(repos.dependencies, repos.topology_nodes)

            for organization_id in await repos.trace_spans.list_organization_ids():
                rows = await repos.trace_spans.list_recent(
                    organization_id, since=window_start, limit=self._span_limit
                )
                if not rows:
                    continue
                spans = [_to_span_record(row) for row in rows]
                _inference, built = await topology.sweep(
                    organization_id,
                    environment=_DEFAULT_ENVIRONMENT,
                    spans=spans,
                    window_seconds=window_seconds,
                    sampling_ratio=None,
                    observed_at=now,
                )
                edges_seen += len(built.edges)
            await session.commit()

        logger.info("topology rebuild completed", extra={"extra_fields": {"edges": edges_seen}})
        return edges_seen


__all__ = ["TopologyRebuildWorker"]
