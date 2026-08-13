"""SLO / SLI computation (docs/064 "SLO / SLI MANAGEMENT").

Pure functions over dataclasses. The service layer fetches windows and
persists results; nothing here touches a database or a clock it was not
given.

**A window with no traffic has no SLI.** This is the single most dangerous
confusion in SLO tooling and the reason :class:`~app.models.enums.SliStatus`
has a ``NO_DATA`` member. Zero good events out of zero valid events is
``0/0``, not ``0.0``, and a platform that reports the latter pages
somebody at 3am because a batch job was idle overnight.

**But an outage that stops traffic must still page.** That is the exact
inverse failure, and it is why :func:`evaluate_burn` does not simply
suppress on no-data: a service returning 5xx to every caller until callers
give up produces a window with no *successful* traffic, and treating "no
data" as "nothing wrong" is how a total outage goes unnoticed. The rule is
that no-data suppresses only when *neither* window saw traffic, and the
long window's earlier traffic keeps the alert alive.

**Direction is part of the objective.** Availability and success rate are
"higher is better"; error rate is "lower is better". A single comparison
serves one of them and silently inverts the other, so the direction is
carried on the objective and every comparison goes through
:meth:`Objective.is_met`.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.models.enums import SliKind, SliStatus

MIN_SAMPLES_FOR_RATIO = 1
"""Below this many valid events, an SLI is ``NO_DATA``. One request that
failed is not a service with 0% availability."""

SECONDS_PER_DAY = 86_400.0

MIN_RELIABLE_COVERAGE = 0.8
"""Share of a period's windows that must have seen traffic before its
compliance figure is worth acting on. A number computed from a fifth of a
month is not a monthly compliance number, and presenting it as one is how
an SLO report becomes decorative."""

DEFAULT_AT_RISK_FRACTION = 0.25
"""Error budget remaining below which an SLO is ``AT_RISK``. A binary
healthy/breaching gives no warning while there is still time to act, which
is the entire purpose of a budget."""


class Direction:
    """Which way is good for an SLI.

    Not an enum because it carries the comparison itself, and an enum plus
    a lookup table is the arrangement that lets the two drift apart.
    """

    HIGHER_IS_BETTER = "higher_is_better"
    LOWER_IS_BETTER = "lower_is_better"


_DIRECTION_BY_KIND: dict[SliKind, str] = {
    SliKind.AVAILABILITY: Direction.HIGHER_IS_BETTER,
    SliKind.SUCCESS_RATE: Direction.HIGHER_IS_BETTER,
    SliKind.LATENCY: Direction.HIGHER_IS_BETTER,
    SliKind.THROUGHPUT: Direction.HIGHER_IS_BETTER,
    SliKind.ERROR_RATE: Direction.LOWER_IS_BETTER,
    SliKind.CUSTOM: Direction.HIGHER_IS_BETTER,
}
"""Latency is ``HIGHER_IS_BETTER`` because a latency *SLI* is the fraction
of requests served within the threshold -- not the latency itself. The
distinction matters: 0.999 of requests under 300ms is an objective, a mean
of 300ms is an average."""


@dataclass(frozen=True, slots=True)
class Objective:
    """What an SLO promises.

    Raises:
        ValueError: On a target outside ``(0, 1)`` for a ratio SLI, or a
            latency SLI with no threshold. A latency objective without a
            threshold is not an objective; it is a request to average
            something, and averaging latency is how a service with a
            terrible tail looks fine.
    """

    kind: SliKind
    target: float
    latency_threshold_ms: float | None = None
    window_days: int = 30
    is_rolling: bool = True

    def __post_init__(self) -> None:
        if not 0.0 < self.target < 1.0:
            raise ValueError(
                f"An SLO target is a fraction strictly between 0 and 1; got {self.target!r}. "
                "A target of exactly 1.0 has a zero error budget and can never be met."
            )
        if self.kind is SliKind.LATENCY and self.latency_threshold_ms is None:
            raise ValueError(
                "A latency SLO needs a threshold in milliseconds -- the boundary that "
                "makes a request good. Without one this is an average, not an objective."
            )

    @property
    def direction(self) -> str:
        return _DIRECTION_BY_KIND.get(self.kind, Direction.HIGHER_IS_BETTER)

    def is_met(self, value: float) -> bool:
        """Whether *value* satisfies this objective.

        Every comparison in this module goes through here. A bare
        ``value >= target`` is correct for availability and exactly
        backwards for error rate.
        """
        if self.direction == Direction.LOWER_IS_BETTER:
            return value <= self.target
        return value >= self.target

    @property
    def budget_fraction(self) -> float:
        """The share of events the objective permits to be bad.

        For a lower-is-better SLI the target *is* the permitted bad share,
        so the budget is the target itself rather than its complement.
        """
        if self.direction == Direction.LOWER_IS_BETTER:
            return self.target
        return 1.0 - self.target


@dataclass(frozen=True, slots=True)
class RatioWindow:
    """Counted events over one window.

    Both counts are kept because a ratio cannot be re-aggregated: the
    availability of two windows is not the mean of their availabilities
    unless both saw identical traffic.
    """

    window_start: datetime
    window_end: datetime
    good_count: int
    total_count: int

    @property
    def duration_seconds(self) -> float:
        return (self.window_end - self.window_start).total_seconds()

    @property
    def has_traffic(self) -> bool:
        return self.total_count >= MIN_SAMPLES_FOR_RATIO


@dataclass(frozen=True, slots=True)
class SliResult:
    """One SLI measurement.

    ``value`` is ``None`` exactly when ``status`` is ``NO_DATA``. Callers
    may rely on that: there is no path that produces a number alongside
    ``NO_DATA`` or a ``None`` alongside any other status.
    """

    status: SliStatus
    value: float | None
    good_count: int
    total_count: int
    window_start: datetime
    window_end: datetime
    reason: str

    @property
    def is_measured(self) -> bool:
        return self.value is not None


def compute_ratio_sli(objective: Objective, window: RatioWindow) -> SliResult:
    """The SLI for a counted window.

    Returns ``NO_DATA`` when the window saw no valid events. That is not a
    degenerate case to be tidied away -- an idle service has an undefined
    availability, and every downstream decision differs between "nothing
    happened" and "everything failed".

    Raises:
        ValueError: When ``good_count`` exceeds ``total_count``, which
            means the caller's query is wrong. Silently clamping it would
            produce an SLI of exactly 1.0 for a broken query, which is the
            most reassuring possible way to be wrong.
    """
    if window.good_count > window.total_count:
        raise ValueError(
            f"good_count ({window.good_count}) exceeds total_count "
            f"({window.total_count}); the query defining good and valid events "
            "disagrees with itself."
        )
    if window.good_count < 0 or window.total_count < 0:
        raise ValueError("Event counts cannot be negative.")

    if not window.has_traffic:
        return SliResult(
            status=SliStatus.NO_DATA,
            value=None,
            good_count=window.good_count,
            total_count=window.total_count,
            window_start=window.window_start,
            window_end=window.window_end,
            reason=(
                "No valid events in this window, so the SLI is undefined. An idle "
                "service is not a failing one."
            ),
        )

    good_ratio = window.good_count / window.total_count
    # For a lower-is-better SLI the measured quantity is the *bad* share.
    value = 1.0 - good_ratio if objective.direction == Direction.LOWER_IS_BETTER else good_ratio
    met = objective.is_met(value)
    return SliResult(
        status=SliStatus.HEALTHY if met else SliStatus.BREACHING,
        value=value,
        good_count=window.good_count,
        total_count=window.total_count,
        window_start=window.window_start,
        window_end=window.window_end,
        reason=(
            f"{window.good_count} of {window.total_count} events good; "
            f"{value:.6f} against a target of {objective.target:.6f}."
        ),
    )


@dataclass(frozen=True, slots=True)
class ErrorBudget:
    """How much failure the objective still permits.

    ``remaining_fraction`` may be negative, deliberately. Clamping an
    overspent budget to zero hides how far past it a service is, and that
    overspend is exactly the number that decides whether to freeze
    releases.
    """

    total_events: int
    allowed_bad_events: float
    actual_bad_events: int
    remaining_events: float
    remaining_fraction: float
    is_exhausted: bool

    @property
    def consumed_fraction(self) -> float:
        """The share of the budget spent. Above 1.0 when overspent."""
        return 1.0 - self.remaining_fraction


def compute_error_budget(objective: Objective, window: RatioWindow) -> ErrorBudget | None:
    """The error budget for a counted window, or ``None`` with no traffic.

    ``None`` rather than a full budget: a budget is a share of observed
    events, and over zero events there is nothing to have a share of.
    Reporting "100% remaining" for an idle service invites exactly the
    wrong conclusion when traffic resumes.
    """
    if not window.has_traffic:
        return None

    allowed = objective.budget_fraction * window.total_count
    actual_bad = window.total_count - window.good_count
    remaining_events = allowed - actual_bad
    remaining_fraction = remaining_events / allowed if allowed > 0 else 0.0

    # ``allowed`` is a float product of a float target and an int count, so
    # a budget of "exactly ten events" materialises as 10.000000000000009.
    # A bare ``remaining <= 0`` therefore reports a budget spent to its last
    # event as still having 9e-15 left -- and "exactly at budget" is a
    # boundary services really do sit on. The tolerance is relative to the
    # budget itself so it scales with the count rather than being a
    # magic epsilon.
    exhausted = remaining_events <= 0 or math.isclose(
        remaining_events, 0.0, abs_tol=max(allowed, 1.0) * 1e-9
    )
    return ErrorBudget(
        total_events=window.total_count,
        allowed_bad_events=allowed,
        actual_bad_events=actual_bad,
        remaining_events=remaining_events,
        remaining_fraction=remaining_fraction,
        is_exhausted=exhausted,
    )


def classify_status(
    objective: Objective,
    sli: SliResult,
    budget: ErrorBudget | None,
    *,
    at_risk_fraction: float = DEFAULT_AT_RISK_FRACTION,
) -> SliStatus:
    """Where an SLO stands, with ``AT_RISK`` between healthy and breaching.

    The order matters: an exhausted budget is reported as ``EXHAUSTED``
    even while the instantaneous SLI is healthy, because a service that
    has already spent the month's budget is not in a healthy position
    however well the last five minutes went.
    """
    if sli.status is SliStatus.NO_DATA or budget is None:
        return SliStatus.NO_DATA
    if budget.is_exhausted:
        return SliStatus.EXHAUSTED
    if sli.value is not None and not objective.is_met(sli.value):
        return SliStatus.BREACHING
    if budget.remaining_fraction < at_risk_fraction:
        return SliStatus.AT_RISK
    return SliStatus.HEALTHY


@dataclass(frozen=True, slots=True)
class BurnRate:
    """How fast the budget is being spent, relative to the rate that would
    exactly exhaust it over the whole SLO window.

    A burn rate of 1.0 spends the budget precisely as the window ends. 14.4
    over an hour exhausts a 30-day budget in about two days.
    """

    window_hours: float
    rate: float | None
    bad_ratio: float | None
    total_count: int
    has_traffic: bool

    @property
    def is_measured(self) -> bool:
        return self.rate is not None


def compute_burn_rate(
    objective: Objective, window: RatioWindow, *, window_hours: float
) -> BurnRate:
    """The burn rate over one window.

    ``rate`` is ``None`` with no traffic -- not zero. Zero would assert
    that the budget is not being consumed, which is a claim about a period
    nothing was observed in.
    """
    if window_hours <= 0:
        raise ValueError(f"A burn window must be positive; got {window_hours!r} hours.")
    if not window.has_traffic:
        return BurnRate(
            window_hours=window_hours,
            rate=None,
            bad_ratio=None,
            total_count=window.total_count,
            has_traffic=False,
        )

    bad_ratio = (window.total_count - window.good_count) / window.total_count
    budget = objective.budget_fraction
    # A zero budget means a target of 1.0, which __post_init__ refuses --
    # so this cannot divide by zero, and asserting that here is cheaper
    # than a reader wondering.
    rate = bad_ratio / budget
    return BurnRate(
        window_hours=window_hours,
        rate=rate,
        bad_ratio=bad_ratio,
        total_count=window.total_count,
        has_traffic=True,
    )


@dataclass(frozen=True, slots=True)
class BurnAlert:
    """The outcome of a multi-window burn-rate evaluation."""

    should_alert: bool
    fast: BurnRate
    slow: BurnRate
    fast_threshold: float
    slow_threshold: float
    reason: str


def evaluate_burn(
    fast: BurnRate,
    slow: BurnRate,
    *,
    fast_threshold: float,
    slow_threshold: float,
) -> BurnAlert:
    """Whether a burn-rate page should fire.

    Both windows must exceed their thresholds. A short window alone fires
    on every transient blip; a long window alone takes hours to notice a
    total outage.

    **No-data does not silence an alert on its own.** A service failing
    every request until its callers give up produces a window with no
    traffic, and treating that as "nothing wrong" is how a total outage
    goes unnoticed. A missing window is only ever a reason not to fire
    when *both* are missing -- and even then the caller is told that the
    evaluation was not possible rather than that everything is fine.
    """
    if not fast.is_measured and not slow.is_measured:
        return BurnAlert(
            should_alert=False,
            fast=fast,
            slow=slow,
            fast_threshold=fast_threshold,
            slow_threshold=slow_threshold,
            reason=(
                "Neither window saw traffic, so no burn rate could be computed. This "
                "is an absence of evidence, not evidence the objective is being met."
            ),
        )

    # A window with no traffic cannot contribute a rate, so it neither
    # triggers nor blocks: the other window decides. This is what keeps a
    # traffic-stopping outage alerting on the long window's earlier data.
    fast_hot = fast.rate is not None and fast.rate >= fast_threshold
    slow_hot = slow.rate is not None and slow.rate >= slow_threshold
    both_measured = fast.is_measured and slow.is_measured

    if both_measured:
        should = fast_hot and slow_hot
        reason = (
            f"fast {fast.rate:.2f}x (>= {fast_threshold}) and "
            f"slow {slow.rate:.2f}x (>= {slow_threshold})."
            if should
            else (
                f"fast {fast.rate:.2f}x vs {fast_threshold}, "
                f"slow {slow.rate:.2f}x vs {slow_threshold}; both must exceed."
            )
        )
        return BurnAlert(
            should_alert=should,
            fast=fast,
            slow=slow,
            fast_threshold=fast_threshold,
            slow_threshold=slow_threshold,
            reason=reason,
        )

    measured = fast if fast.is_measured else slow
    hot = fast_hot if fast.is_measured else slow_hot
    label = "fast" if fast.is_measured else "slow"
    threshold = fast_threshold if fast.is_measured else slow_threshold
    return BurnAlert(
        should_alert=hot,
        fast=fast,
        slow=slow,
        fast_threshold=fast_threshold,
        slow_threshold=slow_threshold,
        reason=(
            f"Only the {label} window saw traffic: {measured.rate:.2f}x against "
            f"{threshold}. A window with no traffic during an outage is expected "
            "and does not suppress the alert."
        ),
    )


def project_exhaustion(
    budget: ErrorBudget | None,
    burn: BurnRate,
    *,
    window_days: int,
    now: datetime,
) -> datetime | None:
    """When the budget runs out at the current burn rate, or ``None``.

    ``None`` when the budget is not being consumed, when it is already
    gone, or when there is no measured rate. A far-future date from a flat
    burn would be an invented prediction, and this is a projection rather
    than a forecast: it assumes the current rate continues, which is
    exactly what an operator should be deciding whether to allow.
    """
    if budget is None or burn.rate is None:
        return None
    if budget.is_exhausted or burn.rate <= 0:
        return None

    # At burn rate r, the whole window's budget is consumed in
    # window_days / r days. What remains goes in that, scaled by the
    # remaining share.
    days_to_full_burn = window_days / burn.rate
    days_remaining = days_to_full_burn * budget.remaining_fraction
    if not math.isfinite(days_remaining) or days_remaining <= 0:
        return None
    return now + timedelta(days=days_remaining)


def rollup_ratio_windows(windows: Sequence[RatioWindow]) -> RatioWindow | None:
    """Combine per-window counts into one window.

    Sums the counts rather than averaging the ratios, which is the whole
    reason both counts are stored. Averaging thirty daily availabilities
    weights a quiet Sunday equally with a busy Monday and produces a
    monthly figure no customer experienced.

    ``None`` for an empty sequence -- there is no window spanning nothing.
    """
    if not windows:
        return None
    ordered = sorted(windows, key=lambda window: window.window_start)
    return RatioWindow(
        window_start=ordered[0].window_start,
        window_end=max(window.window_end for window in ordered),
        good_count=sum(window.good_count for window in ordered),
        total_count=sum(window.total_count for window in ordered),
    )


def latency_window_from_samples(
    samples: Sequence[float],
    *,
    threshold_ms: float,
    window_start: datetime,
    window_end: datetime,
) -> RatioWindow:
    """A counted window from raw latency samples.

    A request exactly at the threshold counts as good: the objective is
    "served **within** 300ms", and excluding the boundary makes the
    recommended remediation -- tuning to land at the threshold --
    ineffective by exactly one sample's worth.
    """
    good = sum(1 for sample in samples if sample <= threshold_ms)
    return RatioWindow(
        window_start=window_start,
        window_end=window_end,
        good_count=good,
        total_count=len(samples),
    )


@dataclass(frozen=True, slots=True)
class ComplianceReport:
    """Compliance over a period, from its constituent windows."""

    window_start: datetime
    window_end: datetime
    status: SliStatus
    value: float | None
    good_count: int
    total_count: int
    measured_window_count: int
    empty_window_count: int
    coverage: float | None
    budget: ErrorBudget | None

    @property
    def is_reliable(self) -> bool:
        """Whether enough of the period was measured to act on the figure.

        A compliance number computed from a fifth of a month is not a
        monthly compliance number, and presenting it as one is how an SLO
        report becomes decorative.
        """
        return self.coverage is not None and self.coverage >= MIN_RELIABLE_COVERAGE


def compute_compliance(
    objective: Objective,
    windows: Sequence[RatioWindow],
    *,
    at_risk_fraction: float = DEFAULT_AT_RISK_FRACTION,
) -> ComplianceReport:
    """Compliance across a period.

    ``coverage`` is the share of windows that saw any traffic, reported
    because it is the difference between "99.9% available" and "99.9%
    available across the fifth of the month we could measure".
    """
    if not windows:
        now = datetime.now(tz=None).astimezone()
        return ComplianceReport(
            window_start=now,
            window_end=now,
            status=SliStatus.NO_DATA,
            value=None,
            good_count=0,
            total_count=0,
            measured_window_count=0,
            empty_window_count=0,
            coverage=None,
            budget=None,
        )

    measured = [window for window in windows if window.has_traffic]
    combined = rollup_ratio_windows(windows)
    assert combined is not None
    sli = compute_ratio_sli(objective, combined)
    budget = compute_error_budget(objective, combined)
    status = classify_status(objective, sli, budget, at_risk_fraction=at_risk_fraction)

    return ComplianceReport(
        window_start=combined.window_start,
        window_end=combined.window_end,
        status=status,
        value=sli.value,
        good_count=combined.good_count,
        total_count=combined.total_count,
        measured_window_count=len(measured),
        empty_window_count=len(windows) - len(measured),
        coverage=len(measured) / len(windows),
        budget=budget,
    )


def burn_threshold_for(*, budget_share: float, window_hours: float, slo_window_days: int) -> float:
    """The burn rate that spends *budget_share* of the budget in the window.

    The arithmetic assumes traffic is uniform over the SLO period. It is
    not -- a diurnal service does most of its work in a third of the day --
    so a threshold derived this way is approximate, and the standard
    14.4 / 6 pair is used by default rather than a derived figure for
    exactly that reason.

    Raises:
        ValueError: On a non-positive window or period.
    """
    if window_hours <= 0 or slo_window_days <= 0:
        raise ValueError("Both the burn window and the SLO period must be positive.")
    period_hours = slo_window_days * 24.0
    return budget_share * period_hours / window_hours


__all__ = [
    "DEFAULT_AT_RISK_FRACTION",
    "MIN_RELIABLE_COVERAGE",
    "MIN_SAMPLES_FOR_RATIO",
    "BurnAlert",
    "BurnRate",
    "ComplianceReport",
    "Direction",
    "ErrorBudget",
    "Objective",
    "RatioWindow",
    "SliResult",
    "burn_threshold_for",
    "classify_status",
    "compute_burn_rate",
    "compute_compliance",
    "compute_error_budget",
    "compute_ratio_sli",
    "latency_window_from_samples",
    "project_exhaustion",
    "rollup_ratio_windows",
]
