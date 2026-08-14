"""The subscription renewal sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

Notifies for trials and subscriptions entering their renewal reminder
window, and expires any subscription that has run out its grace period
without renewing -- a subscription nobody renewed does not silently
keep serving traffic forever past its period end.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.enums import SubscriptionStatus
from app.services.bundle import build_repositories
from app.services.notifications import BillingNotifier
from app.services.subscriptions import SubscriptionService
from app.subscriptions.engine import is_renewal_due, is_within_grace_period
from app.types import EventPublisher

logger = get_logger("app.workers.subscription_renewal_sweep")

_RENEWABLE_STATUSES = frozenset({SubscriptionStatus.ACTIVE, SubscriptionStatus.PENDING_RENEWAL})


class SubscriptionRenewalSweepWorker:
    """Notifies for upcoming renewals/trial expiry, and expires
    subscriptions past their grace period."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        publish_event: EventPublisher,
        notifier: BillingNotifier,
        grace_period_days: int,
        renewal_reminder_days_before: int,
    ) -> None:
        self._session_factory = session_factory
        self._publish_event = publish_event
        self._notifier = notifier
        self._grace_period_days = grace_period_days
        self._renewal_reminder_days_before = renewal_reminder_days_before

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Sweep every organization's subscriptions, returning how many
        were checked."""
        now = datetime.now(UTC)
        checked = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)
            service = SubscriptionService(repos.subscriptions, publish=self._publish_event)

            for organization_id in await repos.subscriptions.list_organization_ids():
                for subscription in await repos.subscriptions.list_recent(
                    organization_id, limit=5000
                ):
                    if subscription.status == SubscriptionStatus.TRIAL:
                        if is_renewal_due(
                            subscription.current_period_end,
                            now=now,
                            reminder_days_before=self._renewal_reminder_days_before,
                        ):
                            days_remaining = max(0, (subscription.current_period_end - now).days)
                            await self._notifier.notify_trial_expiring(
                                subscription_id=str(subscription.id), days_remaining=days_remaining
                            )
                    elif subscription.status in _RENEWABLE_STATUSES:
                        past_grace = now > subscription.current_period_end + timedelta(
                            days=self._grace_period_days
                        )
                        if past_grace:
                            await service.transition(
                                subscription,
                                target=SubscriptionStatus.EXPIRED,
                                actor_id=None,
                                now=now,
                            )
                        elif now >= subscription.current_period_end:
                            if is_within_grace_period(
                                subscription.current_period_end,
                                now=now,
                                grace_period_days=self._grace_period_days,
                            ):
                                await self._notifier.notify_subscription_expiring(
                                    subscription_id=str(subscription.id), days_remaining=0
                                )
                        elif is_renewal_due(
                            subscription.current_period_end,
                            now=now,
                            reminder_days_before=self._renewal_reminder_days_before,
                        ):
                            days_remaining = max(0, (subscription.current_period_end - now).days)
                            await self._notifier.notify_renewal_reminder(
                                subscription_id=str(subscription.id),
                                current_period_end=subscription.current_period_end.isoformat(),
                            )
                            await self._notifier.notify_subscription_expiring(
                                subscription_id=str(subscription.id), days_remaining=days_remaining
                            )
                    checked += 1
            await session.commit()

        logger.info(
            "subscription renewal sweep completed", extra={"extra_fields": {"checked": checked}}
        )
        return checked


__all__ = ["SubscriptionRenewalSweepWorker"]
