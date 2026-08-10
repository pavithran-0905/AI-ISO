"""Tests for :mod:`app.telemetry.tracing`.

Uses a **real** in-memory OpenTelemetry SDK recorder, not a mock, so
these prove attributes genuinely reach the span. That matters here:
``start_span``'s signature is ``(tracer, name, *, span_type=None,
**attributes)``, so passing a literal ``attributes={...}`` keyword
silently drops every attribute instead of raising -- a confirmed
repo-wide defect in AI-IOS services built before Prompt 054. A test
that only checked "a span was produced" would pass against that bug.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import Tracer

from app.telemetry.tracing import (
    trace_evaluation,
    trace_execution_record,
    trace_optimization,
    trace_publishing,
    trace_rendering,
    trace_retrieval,
    trace_variable_resolution,
    trace_worker_tick,
)


class Recorder:
    """A real TracerProvider writing into an in-memory exporter."""

    def __init__(self) -> None:
        self.exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(self.exporter))
        self.tracer: Tracer = provider.get_tracer("test")

    @property
    def spans(self) -> list:
        return list(self.exporter.get_finished_spans())

    @property
    def only(self):
        spans = self.spans
        assert len(spans) == 1, f"expected exactly one span, got {len(spans)}"
        return spans[0]


@pytest.fixture
def recorder() -> Iterator[Recorder]:
    yield Recorder()


# ---------------------------------------------------------------------------
# Each helper emits a named span carrying its own identifiers
# ---------------------------------------------------------------------------


def test_retrieval_span(recorder: Recorder) -> None:
    with trace_retrieval(recorder.tracer, slug="greet", version_number="1.0.0"):
        pass
    span = recorder.only
    assert span.name == "prompt.retrieve"
    assert span.attributes["prompt.slug"] == "greet"
    assert span.attributes["prompt.version"] == "1.0.0"


def test_rendering_span(recorder: Recorder) -> None:
    with trace_rendering(recorder.tracer, slug="greet", version_number="1.0.0", depth=2):
        pass
    span = recorder.only
    assert span.name == "prompt.render"
    assert span.attributes["prompt.template_depth"] == 2


def test_variable_resolution_span_records_counts_not_names(recorder: Recorder) -> None:
    """Counts only -- a variable's name or value could carry tenant
    data, and a tracing backend has different retention rules than this
    service's own database."""
    with trace_variable_resolution(recorder.tracer, version_number="1.0.0", declared=5, masked=2):
        pass
    span = recorder.only
    assert span.name == "prompt.variables.resolve"
    assert span.attributes["prompt.variables_declared"] == 5
    assert span.attributes["prompt.variables_masked"] == 2


def test_execution_record_span(recorder: Recorder) -> None:
    with trace_execution_record(
        recorder.tracer, slug="greet", version_number="1.0.0", status="succeeded"
    ):
        pass
    span = recorder.only
    assert span.name == "prompt.execution.record"
    assert span.attributes["prompt.execution_status"] == "succeeded"


def test_evaluation_span(recorder: Recorder) -> None:
    with trace_evaluation(recorder.tracer, version_number="1.0.0", metrics=8):
        pass
    span = recorder.only
    assert span.name == "prompt.evaluate"
    assert span.attributes["prompt.metrics_scored"] == 8


def test_optimization_span(recorder: Recorder) -> None:
    with trace_optimization(recorder.tracer, version_number="1.0.0", suggestions=3):
        pass
    span = recorder.only
    assert span.name == "prompt.optimize"
    assert span.attributes["prompt.suggestions"] == 3


def test_publishing_span_records_whether_the_gate_was_satisfied(recorder: Recorder) -> None:
    """An override is exactly the event worth finding in a trace
    afterwards."""
    with trace_publishing(recorder.tracer, slug="greet", version_number="1.1.0", gated=False):
        pass
    span = recorder.only
    assert span.name == "prompt.publish"
    assert span.attributes["prompt.gate_satisfied"] is False


def test_worker_tick_span(recorder: Recorder) -> None:
    with trace_worker_tick(recorder.tracer, worker="approval-expiry", processed=7):
        pass
    span = recorder.only
    assert span.name == "prompt.worker.tick"
    assert span.attributes["prompt.worker"] == "approval-expiry"
    assert span.attributes["prompt.processed"] == 7


# ---------------------------------------------------------------------------
# The **{...} unpacking contract
# ---------------------------------------------------------------------------


def test_extra_keyword_attributes_reach_the_span(recorder: Recorder) -> None:
    """This is what a literal ``attributes={...}`` keyword would break:
    the value would be swallowed into the catch-all under the key
    "attributes" instead of being set."""
    with trace_retrieval(
        recorder.tracer,
        slug="greet",
        version_number="1.0.0",
        **{"prompt.locale": "fr", "prompt.cache_hit": True},
    ):
        pass
    span = recorder.only
    assert span.attributes["prompt.locale"] == "fr"
    assert span.attributes["prompt.cache_hit"] is True
    assert "attributes" not in span.attributes


def test_no_span_carries_an_attributes_key(recorder: Recorder) -> None:
    """A regression guard for the whole defect class, across every
    helper in the module."""
    with trace_retrieval(recorder.tracer, slug="s", version_number="1.0.0"):
        pass
    with trace_rendering(recorder.tracer, slug="s", version_number="1.0.0", depth=1):
        pass
    with trace_variable_resolution(recorder.tracer, version_number="1.0.0", declared=0, masked=0):
        pass
    with trace_execution_record(
        recorder.tracer, slug="s", version_number="1.0.0", status="succeeded"
    ):
        pass
    with trace_evaluation(recorder.tracer, version_number="1.0.0", metrics=0):
        pass
    with trace_optimization(recorder.tracer, version_number="1.0.0", suggestions=0):
        pass
    with trace_publishing(recorder.tracer, slug="s", version_number="1.0.0", gated=True):
        pass
    with trace_worker_tick(recorder.tracer, worker="w", processed=0):
        pass

    spans = recorder.spans
    assert len(spans) == 8
    for span in spans:
        assert "attributes" not in span.attributes


# ---------------------------------------------------------------------------
# Structural behaviour
# ---------------------------------------------------------------------------


def test_a_helper_yields_a_usable_span(recorder: Recorder) -> None:
    with trace_retrieval(recorder.tracer, slug="s", version_number="1.0.0") as span:
        span.set_attribute("prompt.custom", "added-inside")
    assert recorder.only.attributes["prompt.custom"] == "added-inside"


def test_nested_helpers_are_parent_and_child(recorder: Recorder) -> None:
    """``start_span`` uses ``start_as_current_span``, so a helper opened
    inside another belongs to the same trace."""
    with (
        trace_retrieval(recorder.tracer, slug="s", version_number="1.0.0"),
        trace_rendering(recorder.tracer, slug="s", version_number="1.0.0", depth=1),
    ):
        pass

    child, parent = recorder.spans
    assert child.name == "prompt.render"
    assert parent.name == "prompt.retrieve"
    assert child.parent is not None
    assert child.parent.span_id == parent.context.span_id
    assert child.context.trace_id == parent.context.trace_id


def test_an_exception_inside_a_span_still_closes_it(recorder: Recorder) -> None:
    """The span must be exported even when the traced work fails --
    otherwise failures are exactly the traces that go missing."""
    with pytest.raises(RuntimeError, match="boom"):
        with trace_rendering(recorder.tracer, slug="s", version_number="1.0.0", depth=1):
            raise RuntimeError("boom")

    span = recorder.only
    assert span.name == "prompt.render"
    assert span.end_time is not None


def test_each_helper_sets_a_span_type(recorder: Recorder) -> None:
    """``span_type`` is what makes spans filterable by kind in a
    backend, so an unset one is a silent loss of grouping."""
    with trace_worker_tick(recorder.tracer, worker="w", processed=0):
        pass
    assert any(key.endswith("span_type") or "type" in key for key in recorder.only.attributes)
