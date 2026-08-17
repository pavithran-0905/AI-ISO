"""AI documentation assistant answer selection.

**A declared seam.** docs/074 says "Integrate Prompt 060 [AI Agent
Platform]. Integrate Prompt 062 [RAG Service]" for the AI documentation
assistant -- but no AI-IOS service in this codebase calls another over
live HTTP; every cross-service "integration" so far is either an event/
notification wiring or a reused conceptual pattern. Consistent with
that, this module is the same kind of seam
``services/public-api-platform``'s Webhook Failure notification is:
fully implemented and tested on its own terms (reusing
``app.search.engine``'s relevance scoring to pick the best-matching
indexed page for a question), with the real RAG/agent call a full
deployment would make left as the thing this function's return value
would hand off to.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.search.engine import SearchCandidate, score_candidate

_NO_MATCH_MESSAGE = (
    "No indexed documentation matched this question closely enough to answer confidently."
)


@dataclass(frozen=True, slots=True)
class AssistantAnswer:
    content_id: str | None
    title: str | None
    confidence: float
    message: str


def answer_question(
    question: str,
    candidates: Sequence[tuple[str, SearchCandidate]],
    *,
    confidence_threshold: float = 0.5,
) -> AssistantAnswer:
    """Select the best-matching indexed page for *question*, or report
    no confident match.

    A confident answer names the matching content id so the caller can
    resolve and return its full content; an unconfident one returns
    ``content_id=None`` rather than guessing.
    """
    if not candidates:
        return AssistantAnswer(
            content_id=None, title=None, confidence=0.0, message=_NO_MATCH_MESSAGE
        )

    scored = [
        (identifier, candidate, score_candidate(question, candidate))
        for identifier, candidate in candidates
    ]
    best_id, best_candidate, best_score = max(scored, key=lambda entry: entry[2])

    if best_score < confidence_threshold:
        return AssistantAnswer(
            content_id=None, title=None, confidence=best_score, message=_NO_MATCH_MESSAGE
        )
    return AssistantAnswer(
        content_id=best_id,
        title=best_candidate.title,
        confidence=best_score,
        message=f"Best match: {best_candidate.title!r}.",
    )


__all__ = ["AssistantAnswer", "answer_question"]
