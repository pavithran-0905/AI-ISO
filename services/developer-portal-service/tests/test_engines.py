"""Unit tests for every pure engine module -- the same checks the
hand-verification script already ran, formalized as pytest so they
gate CI, plus edge cases the script didn't cover."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.analytics.engine import engagement_rate, growth_rate
from app.assistant.engine import answer_question
from app.community.engine import TransitionRefusal as CommunityTransitionRefusal
from app.community.engine import compute_reputation_delta
from app.community.engine import validate_transition as validate_community_transition
from app.documentation.engine import TransitionRefusal as ContentTransitionRefusal
from app.documentation.engine import validate_transition as validate_content_transition
from app.explorer.engine import (
    classify_webhook_response,
    compute_webhook_signature,
    is_well_formed_graphql_query,
    verify_webhook_signature,
)
from app.models.enums import (
    CommunityPostStatus,
    ContentStatus,
    PluginSubmissionStatus,
    TutorialDifficulty,
    WebhookTestStatus,
)
from app.playground.engine import is_playground_session_stale
from app.plugins.engine import TransitionRefusal as PluginTransitionRefusal
from app.plugins.engine import compute_checksum, verify_checksum
from app.plugins.engine import validate_transition as validate_plugin_transition
from app.portal.engine import is_session_expired
from app.search.engine import SearchCandidate, rank_candidates, score_candidate
from app.tutorials.engine import is_appropriate_next_difficulty, total_estimated_minutes

NOW = datetime(2026, 8, 14, 12, 0, 0, tzinfo=UTC)


class TestDocumentationEngine:
    def test_draft_to_published(self) -> None:
        assert validate_content_transition(ContentStatus.DRAFT, ContentStatus.PUBLISHED).is_allowed

    def test_published_to_archived(self) -> None:
        assert validate_content_transition(
            ContentStatus.PUBLISHED, ContentStatus.ARCHIVED
        ).is_allowed

    def test_archived_to_draft_revival(self) -> None:
        assert validate_content_transition(ContentStatus.ARCHIVED, ContentStatus.DRAFT).is_allowed

    def test_archived_to_published_refused(self) -> None:
        result = validate_content_transition(ContentStatus.ARCHIVED, ContentStatus.PUBLISHED)
        assert not result.is_allowed
        assert result.refusal == ContentTransitionRefusal.INVALID_TRANSITION

    def test_coerces_plain_strings(self) -> None:
        assert validate_content_transition("draft", "published").is_allowed  # type: ignore[arg-type]


class TestPortalAndPlaygroundEngines:
    def test_session_not_expired_before_expiry(self) -> None:
        assert not is_session_expired(expires_at=NOW + timedelta(hours=1), now=NOW)

    def test_session_expired_after_expiry(self) -> None:
        assert is_session_expired(expires_at=NOW - timedelta(seconds=1), now=NOW)

    def test_playground_stale(self) -> None:
        assert is_playground_session_stale(
            last_active_at=NOW - timedelta(hours=3), now=NOW, max_age_hours=2
        )

    def test_playground_not_stale(self) -> None:
        assert not is_playground_session_stale(
            last_active_at=NOW - timedelta(minutes=30), now=NOW, max_age_hours=2
        )


class TestExplorerEngine:
    def test_webhook_signature_round_trip(self) -> None:
        sig = compute_webhook_signature(payload_bytes=b'{"x":1}', secret="s3cr3t")
        assert verify_webhook_signature(payload_bytes=b'{"x":1}', secret="s3cr3t", signature=sig)

    def test_webhook_signature_rejects_wrong_secret(self) -> None:
        sig = compute_webhook_signature(payload_bytes=b'{"x":1}', secret="s3cr3t")
        assert not verify_webhook_signature(payload_bytes=b'{"x":1}', secret="wrong", signature=sig)

    def test_classify_2xx_succeeded(self) -> None:
        assert classify_webhook_response(204) == WebhookTestStatus.SUCCEEDED

    def test_classify_non_2xx_failed(self) -> None:
        assert classify_webhook_response(500) == WebhookTestStatus.FAILED
        assert classify_webhook_response(199) == WebhookTestStatus.FAILED

    def test_graphql_well_formed(self) -> None:
        assert is_well_formed_graphql_query("{ hello }")

    def test_graphql_rejects_empty(self) -> None:
        assert not is_well_formed_graphql_query("   ")

    def test_graphql_rejects_missing_braces(self) -> None:
        assert not is_well_formed_graphql_query("hello")


class TestPluginsEngine:
    def test_submitted_to_validating(self) -> None:
        assert validate_plugin_transition(
            PluginSubmissionStatus.SUBMITTED, PluginSubmissionStatus.VALIDATING
        ).is_allowed

    def test_approved_terminal(self) -> None:
        result = validate_plugin_transition(
            PluginSubmissionStatus.APPROVED, PluginSubmissionStatus.REJECTED
        )
        assert not result.is_allowed
        assert result.refusal == PluginTransitionRefusal.TERMINAL_STATE

    def test_rejected_to_submitted_resubmission(self) -> None:
        assert validate_plugin_transition(
            PluginSubmissionStatus.REJECTED, PluginSubmissionStatus.SUBMITTED
        ).is_allowed

    def test_checksum_round_trip(self) -> None:
        checksum = compute_checksum(b"plugin bytes")
        assert verify_checksum(b"plugin bytes", expected_checksum=checksum)

    def test_checksum_rejects_tampered_content(self) -> None:
        checksum = compute_checksum(b"plugin bytes")
        assert not verify_checksum(b"tampered", expected_checksum=checksum)


class TestCommunityEngine:
    def test_open_to_answered(self) -> None:
        assert validate_community_transition(
            CommunityPostStatus.OPEN, CommunityPostStatus.ANSWERED
        ).is_allowed

    def test_closed_to_open_reopen(self) -> None:
        assert validate_community_transition(
            CommunityPostStatus.CLOSED, CommunityPostStatus.OPEN
        ).is_allowed

    def test_invalid_transition_refused(self) -> None:
        # Every CommunityPostStatus has at least one allowed next state,
        # so there is no truly-refused pair among the three states other
        # than a state transitioning to itself.
        result = validate_community_transition(CommunityPostStatus.OPEN, CommunityPostStatus.OPEN)
        assert not result.is_allowed
        assert result.refusal == CommunityTransitionRefusal.INVALID_TRANSITION

    def test_reputation_basic(self) -> None:
        assert compute_reputation_delta(upvotes=5, is_accepted_answer=False) == 5

    def test_reputation_with_accepted_bonus(self) -> None:
        assert compute_reputation_delta(upvotes=5, is_accepted_answer=True) == 20


class TestSearchAndAssistantEngines:
    CANDIDATE = SearchCandidate(
        title="Getting Started with Webhooks",
        summary="How to configure webhooks",
        keywords=["webhook", "setup"],
    )

    def test_score_positive_for_matching_query(self) -> None:
        assert score_candidate("webhook setup", self.CANDIDATE) > 0

    def test_score_zero_for_empty_query(self) -> None:
        assert score_candidate("", self.CANDIDATE) == 0.0

    def test_ranking_excludes_zero_score_entries(self) -> None:
        ranked = rank_candidates(
            "webhook",
            [
                ("a", self.CANDIDATE),
                ("b", SearchCandidate(title="Unrelated", summary="", keywords=[])),
            ],
        )
        assert len(ranked) == 1
        assert ranked[0][0] == "a"

    def test_assistant_answers_confidently(self) -> None:
        answer = answer_question("how do I set up webhooks", [("a", self.CANDIDATE)])
        assert answer.content_id == "a"

    def test_assistant_declines_on_weak_match(self) -> None:
        answer = answer_question(
            "how do I set up webhooks",
            [("a", SearchCandidate(title="Unrelated", summary="", keywords=[]))],
        )
        assert answer.content_id is None

    def test_assistant_declines_with_no_candidates(self) -> None:
        answer = answer_question("anything", [])
        assert answer.content_id is None


class TestTutorialsEngine:
    def test_total_estimated_minutes(self) -> None:
        assert total_estimated_minutes([10, 20, 30]) == 60

    def test_total_estimated_minutes_empty(self) -> None:
        assert total_estimated_minutes([]) == 0

    def test_beginner_to_intermediate_appropriate(self) -> None:
        assert is_appropriate_next_difficulty(
            TutorialDifficulty.BEGINNER, TutorialDifficulty.INTERMEDIATE
        )

    def test_beginner_to_advanced_not_appropriate(self) -> None:
        assert not is_appropriate_next_difficulty(
            TutorialDifficulty.BEGINNER, TutorialDifficulty.ADVANCED
        )

    def test_advanced_back_to_beginner_fine(self) -> None:
        assert is_appropriate_next_difficulty(
            TutorialDifficulty.ADVANCED, TutorialDifficulty.BEGINNER
        )


class TestAnalyticsEngine:
    def test_engagement_rate(self) -> None:
        assert engagement_rate(25, 100) == pytest.approx(0.25)

    def test_engagement_rate_empty(self) -> None:
        assert engagement_rate(0, 0) == 0.0

    def test_growth_rate(self) -> None:
        assert growth_rate(100, 150) == pytest.approx(0.5)

    def test_growth_rate_from_zero_with_growth(self) -> None:
        assert growth_rate(0, 10) == 1.0

    def test_growth_rate_from_zero_with_none(self) -> None:
        assert growth_rate(0, 0) == 0.0
