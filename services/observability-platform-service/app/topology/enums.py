"""Vocabulary for service topology."""

from __future__ import annotations

from enum import StrEnum


class SpanKindLabel(StrEnum):
    """OpenTelemetry span kinds, as topology cares about them."""

    SERVER = "server"
    CLIENT = "client"
    PRODUCER = "producer"
    CONSUMER = "consumer"
    INTERNAL = "internal"


class TopologyEdgeKind(StrEnum):
    """What kind of dependency an edge is.

    Async is a *different* edge, not a weaker sync one. Queue dwell time
    is not caller-blocking latency, and a consumer being down does not
    take its producer down -- so async edges carry no duration and are
    excluded from hard blast radius.
    """

    SYNC_CALL = "sync_call"
    ASYNC_MESSAGE = "async_message"


class EdgeEvidenceKind(StrEnum):
    """How a boundary crossing was witnessed, strongest first.

    Each carries its own misattribution rate, which is what makes mixed
    evidence combinable without pretending a peer attribute is as good as
    a parent link.
    """

    SERVER_CHILD_OF_CLIENT = "server_child_of_client"
    SERVER_CHILD_OF_REMOTE = "server_child_of_remote"
    PRODUCER_CONSUMER_LINK = "producer_consumer_link"
    CLIENT_PEER_ATTRIBUTE = "client_peer_attribute"


class ConfidenceBand(StrEnum):
    """Coarse bands over existence confidence, for filtering."""

    PROVEN = "proven"
    LIKELY = "likely"
    WEAK = "weak"


class CriticalityInput(StrEnum):
    """What makes a node critical, kept as named inputs not one score.

    A single "criticality: 0.87" cannot be argued with; "dominates 14
    services and has no observed alternative path" can.
    """

    DOMINATES_MANY = "dominates_many"
    HIGH_FAN_IN = "high_fan_in"
    NO_ALTERNATIVE_PATH = "no_alternative_path"
    IN_CYCLE = "in_cycle"
    ON_CRITICAL_PATH = "on_critical_path"
    UNOBSERVED_DEPENDENTS = "unobserved_dependents"


__all__ = [
    "ConfidenceBand",
    "CriticalityInput",
    "EdgeEvidenceKind",
    "SpanKindLabel",
    "TopologyEdgeKind",
]
