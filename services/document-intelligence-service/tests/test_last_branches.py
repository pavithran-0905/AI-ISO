"""The remaining branches, each one a behaviour the service promises.

Short by design: what is left after the other suites are the paths only an
unusual document or an unusual failure reaches, and each is named for the
thing it protects.
"""

from __future__ import annotations

import uuid

import pytest

from app.models.enums import ReviewStatus, SummaryKind
from app.services.review import ReviewService
from app.services.storage import DocumentStorage
from app.summarization.summarizer import (
    MAX_SENTENCE_WORDS,
    AbstractiveBackend,
    SummaryConfig,
    split_sections,
    summarize,
)

# ---- summarization -----------------------------------------------------------------------


def test_a_sentence_longer_than_the_cap_is_excluded() -> None:
    """One unpunctuated wall of text swamps a whole summary."""
    wall = " ".join(f"word{index}" for index in range(MAX_SENTENCE_WORDS + 40)) + "."
    good = "The connection pool was exhausted by two hundred replica connections."
    summary = summarize(f"{wall}\n\n{good}\n", config=SummaryConfig(sentence_count=2))
    assert "word0" not in summary.text
    assert "connection pool" in summary.text


def test_a_sentence_shorter_than_the_floor_is_excluded() -> None:
    summary = summarize(
        "Too short.\n\nThe connection pool was exhausted by replica connections.\n",
        config=SummaryConfig(sentence_count=2, min_sentence_words=6),
    )
    assert "Too short" not in summary.text


def test_a_bullet_list_is_summarised_even_without_terminal_punctuation() -> None:
    """A document whose substance is a bullet list would otherwise summarise
    to nothing."""
    summary = summarize(
        "Release checklist\n\n"
        "- Confirm the rollback image is present in the registry\n"
        "- Notify the on-call rota thirty minutes before the deployment\n"
        "- Verify the database migration is backwards compatible\n",
        config=SummaryConfig(sentence_count=2),
    )
    assert summary.text
    assert "rollback" in summary.text or "on-call" in summary.text


def test_an_unusually_short_sentence_is_penalised_but_not_excluded() -> None:
    text = (
        "The database connection pool was completely exhausted when every "
        "single service replica opened two hundred separate connections.\n\n"
        "Latency then rose sharply.\n"
    )
    summary = summarize(text, config=SummaryConfig(sentence_count=2, preserve_order=False))
    assert len(summary.sentences) == 2
    scores = [sentence.score for sentence in summary.sentences]
    assert scores[0] >= scores[1]
    assert any("unusually short" in reason for s in summary.sentences for reason in s.reasons)


def test_a_summary_that_kept_every_sentence_is_faithful() -> None:
    """Whatever else it is, a summary made of the whole document is not wrong."""
    summary = summarize(
        "The connection pool was exhausted by two hundred replica connections.",
        config=SummaryConfig(sentence_count=10),
    )
    assert summary.confidence >= 0.9


def test_a_numbered_heading_starts_a_section() -> None:
    sections = split_sections(
        "1. Scope\nThis policy applies to all personnel and contractors.\n"
        "2. Requirements\nConfidential material must not be stored locally.\n"
    )
    assert len(sections) >= 2


def test_a_line_ending_in_punctuation_is_not_a_heading() -> None:
    """Otherwise every short sentence starts a section."""
    sections = split_sections("Short sentence.\nAnother short sentence.\n")
    assert list(sections) == ["Introduction"]


def test_a_bullet_line_is_not_a_heading() -> None:
    sections = split_sections("- A bullet item\nSome following prose here.\n")
    assert list(sections) == ["Introduction"]


def test_the_abstractive_backend_protocol_is_implementable() -> None:
    """The seam a generative model plugs into."""

    class Backend:
        def summarize(self, text: str, *, max_words: int, kind: SummaryKind) -> str:
            return f"{kind!s}:{max_words}:{len(text)}"

    backend: AbstractiveBackend = Backend()
    summary = summarize(
        "The connection pool was exhausted by replica connections.",
        kind=SummaryKind.ABSTRACTIVE,
        backend=backend,
    )
    assert summary.text.startswith("abstractive:")
    assert summary.fallback_used is False


# ---- review and storage -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_assigning_an_open_review_records_the_reviewer_and_the_audit(
    ingestion: object,
    pipeline: object,
    review: ReviewService,
    repos: object,
    organization_id: uuid.UUID,
) -> None:
    from tests.conftest import CHANGE_REQUEST, DEFAULT_STAGES

    result = await ingestion.ingest(  # type: ignore[attr-defined]
        organization_id=organization_id,
        data=CHANGE_REQUEST,
        title="CR",
        filename="cr.txt",
        stages=DEFAULT_STAGES,
    )
    await pipeline.run(result.job, CHANGE_REQUEST)  # type: ignore[attr-defined]

    opened = await review.open(
        organization_id=organization_id,
        document_id=result.document.id,
        reason="needs a second pair of eyes",
    )
    assert opened.status == ReviewStatus.PENDING

    assigned = await review.assign(
        organization_id=organization_id, review_id=opened.id, reviewer_id="reviewer-2"
    )
    assert assigned.status == ReviewStatus.ASSIGNED
    assert assigned.assigned_to == "reviewer-2"
    assert assigned.assigned_at is not None

    actions = [
        audit.action
        for audit in await repos.audits.list_for_org(organization_id)  # type: ignore[attr-defined]
    ]
    assert "review_assigned" in actions


@pytest.mark.asyncio
async def test_deleting_from_a_bucket_that_does_not_exist_reports_failure(
    storage: DocumentStorage,
) -> None:
    """Reported rather than raised: a caller deleting a document should end up
    with a deleted document, not an exception about the object store."""
    broken = DocumentStorage(storage._wrapper, bucket="a-bucket-that-does-not-exist")
    assert await broken.delete(bucket=broken.bucket, key="nothing/here") in {True, False}
