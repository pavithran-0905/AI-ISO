"""Prompt management telemetry (docs/061 "TELEMETRY"): Prompt
Retrieval, Rendering, Variable Resolution, Execution, Evaluation,
Optimization, Publishing.

Integrates ``shared_core.telemetry`` (Prompt 024).

**Every call below passes attributes via ``**{...}``, never a literal
``attributes={...}`` keyword.** ``start_span``'s own signature is
``start_span(tracer, name, *, span_type=None, **attributes)`` -- there
is no parameter actually named ``attributes``, only that catch-all.
Passing one anyway silently drops every attribute onto the floor
instead of raising, a confirmed repo-wide defect in AI-IOS services
built before Prompt 054. This copy was written correct from the start.

**Spans carry identifiers and counts, never prompt text, rendered
output, or resolved variable values.** A prompt body can contain a
tenant's proprietary instructions and a rendered one can contain a
resolved secret; a tracing backend has different retention and access
rules than this service's own database does.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from opentelemetry.trace import Span, Tracer
from shared_core.telemetry.span import SpanType, start_span


@contextmanager
def trace_retrieval(
    tracer: Tracer, *, slug: str, version_number: str, **attributes: object
) -> Iterator[Span]:
    """Span one prompt resolution by slug ("Prompt Retrieval")."""
    with start_span(
        tracer,
        "prompt.retrieve",
        span_type=SpanType.DATABASE_QUERY,
        **{"prompt.slug": slug, "prompt.version": version_number, **attributes},
    ) as span:
        yield span


@contextmanager
def trace_rendering(
    tracer: Tracer, *, slug: str, version_number: str, depth: int, **attributes: object
) -> Iterator[Span]:
    """Span one template render ("Rendering")."""
    with start_span(
        tracer,
        "prompt.render",
        span_type=SpanType.WORKFLOW_STEP,
        **{
            "prompt.slug": slug,
            "prompt.version": version_number,
            "prompt.template_depth": depth,
            **attributes,
        },
    ) as span:
        yield span


@contextmanager
def trace_variable_resolution(
    tracer: Tracer, *, version_number: str, declared: int, masked: int, **attributes: object
) -> Iterator[Span]:
    """Span one variable-resolution pass ("Variable Resolution").

    Records how many variables were declared and how many were masked
    -- never their names or values.
    """
    with start_span(
        tracer,
        "prompt.variables.resolve",
        span_type=SpanType.VALIDATION_STEP,
        **{
            "prompt.version": version_number,
            "prompt.variables_declared": declared,
            "prompt.variables_masked": masked,
            **attributes,
        },
    ) as span:
        yield span


@contextmanager
def trace_execution_record(
    tracer: Tracer, *, slug: str, version_number: str, status: str, **attributes: object
) -> Iterator[Span]:
    """Span recording one production execution ("Execution")."""
    with start_span(
        tracer,
        "prompt.execution.record",
        span_type=SpanType.AI_REQUEST,
        **{
            "prompt.slug": slug,
            "prompt.version": version_number,
            "prompt.execution_status": status,
            **attributes,
        },
    ) as span:
        yield span


@contextmanager
def trace_evaluation(
    tracer: Tracer, *, version_number: str, metrics: int, **attributes: object
) -> Iterator[Span]:
    """Span one evaluation run ("Evaluation")."""
    with start_span(
        tracer,
        "prompt.evaluate",
        span_type=SpanType.VALIDATION_STEP,
        **{"prompt.version": version_number, "prompt.metrics_scored": metrics, **attributes},
    ) as span:
        yield span


@contextmanager
def trace_optimization(
    tracer: Tracer, *, version_number: str, suggestions: int, **attributes: object
) -> Iterator[Span]:
    """Span one optimization analysis ("Optimization")."""
    with start_span(
        tracer,
        "prompt.optimize",
        span_type=SpanType.WORKFLOW_STEP,
        **{"prompt.version": version_number, "prompt.suggestions": suggestions, **attributes},
    ) as span:
        yield span


@contextmanager
def trace_publishing(
    tracer: Tracer, *, slug: str, version_number: str, gated: bool, **attributes: object
) -> Iterator[Span]:
    """Span one publish ("Publishing").

    ``gated`` records whether the publication gate was satisfied
    normally or overridden -- an override is exactly the event worth
    finding in a trace afterwards.
    """
    with start_span(
        tracer,
        "prompt.publish",
        span_type=SpanType.WORKFLOW_STEP,
        **{
            "prompt.slug": slug,
            "prompt.version": version_number,
            "prompt.gate_satisfied": gated,
            **attributes,
        },
    ) as span:
        yield span


@contextmanager
def trace_worker_tick(
    tracer: Tracer, *, worker: str, processed: int, **attributes: object
) -> Iterator[Span]:
    """Span one background worker's sweep tick."""
    with start_span(
        tracer,
        "prompt.worker.tick",
        span_type=SpanType.BACKGROUND_JOB,
        **{"prompt.worker": worker, "prompt.processed": processed, **attributes},
    ) as span:
        yield span


__all__ = [
    "trace_evaluation",
    "trace_execution_record",
    "trace_optimization",
    "trace_publishing",
    "trace_rendering",
    "trace_retrieval",
    "trace_variable_resolution",
    "trace_worker_tick",
]
