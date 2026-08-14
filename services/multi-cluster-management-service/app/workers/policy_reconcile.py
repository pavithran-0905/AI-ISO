"""The policy reconciliation worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Times out any policy stuck ``PENDING``/``PROPAGATING`` past its
propagation timeout, marking it ``FAILED`` -- a propagation that never
confirmed one way or the other should not sit forever looking "in
progress." Actually re-checking an ``APPLIED`` policy's live drift state
against the cluster is target-specific work this build does not wire a
client for (see :func:`app.policies.engine.detect_drift`, which needs a
live state hash this worker has no way to obtain); this worker only
touches ``last_checked_at`` for applied policies due their next check,
which keeps the "when was this last looked at" bookkeeping honest
without fabricating a drift verdict from nothing.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.enums import PolicyPropagationStatus
from app.services.bundle import build_repositories
from app.services.notifications import FleetNotifier

logger = get_logger("app.workers.policy_reconcile")


class PolicyReconcileWorker:
    """Times out stuck propagations and refreshes applied policies' due
    dates."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        notifier: FleetNotifier,
        propagation_timeout_seconds: float,
        drift_check_interval_seconds: int,
    ) -> None:
        self._session_factory = session_factory
        self._notifier = notifier
        self._propagation_timeout = timedelta(seconds=propagation_timeout_seconds)
        self._drift_check_interval = timedelta(seconds=drift_check_interval_seconds)

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Time out stuck propagations, returning how many were failed."""
        now = datetime.now(UTC)
        timed_out = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)

            for organization_id in await repos.policies.list_organization_ids():
                for policy in await repos.policies.list_pending(organization_id):
                    if now - policy.created_at >= self._propagation_timeout:
                        policy.propagation_status = PolicyPropagationStatus.FAILED
                        policy.last_checked_at = now
                        await repos.policies.update(policy)
                        if policy.cluster_id is not None:
                            await self._notifier.notify_policy_violation(
                                cluster_id=str(policy.cluster_id),
                                policy_id=str(policy.id),
                                policy_name=policy.name,
                            )
                        timed_out += 1

                for policy in await repos.policies.list_applied(organization_id):
                    due = (
                        policy.last_checked_at is None
                        or now - policy.last_checked_at >= self._drift_check_interval
                    )
                    if due:
                        policy.last_checked_at = now
                        await repos.policies.update(policy)
            await session.commit()

        logger.info("policy reconcile completed", extra={"extra_fields": {"timed_out": timed_out}})
        return timed_out


__all__ = ["PolicyReconcileWorker"]
