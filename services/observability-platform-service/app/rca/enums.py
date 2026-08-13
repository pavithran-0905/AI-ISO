"""Vocabulary for root cause analysis.

This engine correlates; it does not establish causation. Every name here
is chosen so that a reader cannot mistake the second for the first, and
so that "we could not measure this" never collapses into "we measured
this and it was zero".
"""

from __future__ import annotations

from enum import StrEnum


class ClockSource(StrEnum):
    """Whose clock stamped a signal.

    Agent-stamped and ingest-stamped times are not comparable at the same
    tolerance: ingest lag is queue depth, not clock error, and moves by
    minutes under load. Comparing them silently is how a two-second skew
    budget gets applied to a four-minute discrepancy.
    """

    AGENT = "agent"
    INGEST = "ingest"
    EXTERNAL = "external"


class PrecedenceVerdict(StrEnum):
    """Whether one event can be said to have come before another.

    Three-valued, because a one-sided ``cause.at <= effect.at + tol``
    reports an event 1.9 seconds *after* its effect as preceding it --
    and passes every test written with a ten-second gap.
    """

    PRECEDES = "precedes"
    FOLLOWS = "follows"
    INDETERMINATE = "indeterminate"


class Unmeasurable(StrEnum):
    """Why a correlation coefficient does not exist.

    Each member is a case where returning a number would assert
    something. ``0.0`` says "no relationship"; the truth is "no
    information", and a service that scores 0.0 ranks last and looks
    checked.
    """

    TOO_FEW_PAIRED_BUCKETS = "too_few_paired_buckets"
    BOTH_SERIES_NEVER_ACTIVE = "both_series_never_active"
    """Two silent services score a perfect Jaccard under the reasonable
    guard ``if not union: return 1.0``."""
    ONE_SERIES_CONSTANT = "one_series_constant"
    UNOBSERVABLE = "unobservable"
    """No instrumentation at all. Collapsing this into a count of zero
    turns "we cannot see it" into "it is fine", and the service is then
    never investigated."""
    PLATFORM_GAP = "platform_gap"


class EvidenceTier(StrEnum):
    """How much a candidate is supported, on a deliberately coarse scale.

    There is no composite score anywhere in this engine. A single number
    ranks coincidence above mechanism, invites thresholding into a causal
    claim, and forces missing evidence to be imputed.
    """

    MECHANISM_AND_TIMING = "mechanism_and_timing"
    TIMING_ONLY = "timing_only"
    MECHANISM_ONLY = "mechanism_only"
    COINCIDENT = "coincident"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class Direction(StrEnum):
    """Which way a graph traversal runs.

    Named rather than implied because the inversion -- blast radius over
    dependencies, or candidates drawn from dependents -- is plausible
    from either end, and a line-graph unit test passes if the author and
    the reviewer share the confusion.
    """

    UPSTREAM = "upstream"
    DOWNSTREAM = "downstream"


class EdgeKind(StrEnum):
    """What sort of call an edge represents.

    Determines the lag budget. An async consumer symptomatic four minutes
    later is either wrongly excluded or included with a fabricated lag if
    every edge shares one ceiling.
    """

    SYNCHRONOUS = "synchronous"
    ASYNCHRONOUS = "asynchronous"
    CACHE = "cache"
    DATASTORE = "datastore"
    DECLARED = "declared"


class PathQuality(StrEnum):
    """How well-evidenced a path through the graph is."""

    CORROBORATED = "corroborated"
    OBSERVED_ONLY = "observed_only"
    DECLARED_ONLY = "declared_only"
    """A manifest edge that has carried no traffic in months can reach
    half the estate. It can never yield CORROBORATED."""


class BlastBucket(StrEnum):
    """How a downstream service was classified.

    Three buckets and no aggregate total: whichever way uninstrumented
    services are folded into one number, the number misleads.
    """

    OBSERVED_AFFECTED = "observed_affected"
    OBSERVED_HEALTHY = "observed_healthy"
    UNOBSERVABLE = "unobservable"


class RecommendationKind(StrEnum):
    """What to do next -- always to acquire or verify evidence.

    Deliberately contains no remediation. "Roll back payments-api"
    asserts a cause that no tier claimed.
    """

    WIDEN_WINDOW = "widen_window"
    EXPAND_GRAPH = "expand_graph"
    INSTRUMENT_SERVICE = "instrument_service"
    CHECK_CHANGE_LOG = "check_change_log"
    COLLECT_TRACES = "collect_traces"
    VERIFY_CLOCK_SYNC = "verify_clock_sync"
    SEPARATE_CONFOUNDED = "separate_confounded"


class AnalysisRefusal(StrEnum):
    """Why an analysis produced no ranking at all."""

    NO_SIGNALS = "no_signals"
    NO_CANDIDATES = "no_candidates"
    PLATFORM_WIDE_GAP = "platform_wide_gap"
    WINDOW_TOO_SHORT = "window_too_short"


class WindowProvenance(StrEnum):
    """Where the analysis window came from.

    A window derived from an alert, with that alert's own service left in
    the candidate pool, produces perfect self-correlation. The provenance
    is what lets the engine exclude it.
    """

    OPERATOR_SUPPLIED = "operator_supplied"
    DERIVED_FROM_SIGNAL = "derived_from_signal"
    DERIVED_FROM_INCIDENT = "derived_from_incident"


__all__ = [
    "AnalysisRefusal",
    "BlastBucket",
    "ClockSource",
    "Direction",
    "EdgeKind",
    "EvidenceTier",
    "PathQuality",
    "PrecedenceVerdict",
    "RecommendationKind",
    "Unmeasurable",
    "WindowProvenance",
]
