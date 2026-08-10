"""Tests for :mod:`app.evaluation.scoring`.

Pure module. Every scorer is deterministic and model-free, so these
assert exact values rather than ranges -- that determinism is the whole
reason the scorers are shaped the way they are.
"""

from __future__ import annotations

import pytest

from app.evaluation.scoring import (
    MIN_CONSISTENCY_SAMPLES,
    EvaluationReport,
    MetricScore,
    evaluate,
    score_completeness,
    score_consistency,
    score_cost,
    score_custom,
    score_hallucination_risk,
    score_latency,
    score_response_accuracy,
    score_safety,
    score_token_usage,
)
from app.models.enums import EvaluationMetric

SYNTHETIC_PRIVATE_KEY = "-----BEGIN PRIVATE KEY-----\nMIIBVQ==\n-----END PRIVATE KEY-----"


def metrics(report: EvaluationReport) -> list[EvaluationMetric]:
    return [score.metric for score in report.scores]


# ---------------------------------------------------------------------------
# response accuracy
# ---------------------------------------------------------------------------


def test_identical_text_scores_one() -> None:
    assert score_response_accuracy("the cat sat", "the cat sat").score == 1.0


def test_disjoint_text_scores_zero() -> None:
    assert score_response_accuracy("alpha beta", "gamma delta").score == 0.0


def test_partial_overlap_is_a_jaccard_index() -> None:
    """{a,b,c} vs {b,c,d}: 2 shared of 4 distinct."""
    assert score_response_accuracy("a b c", "b c d").score == pytest.approx(0.5)


def test_differently_worded_but_overlapping_is_not_a_total_failure() -> None:
    """Exact-match scoring would give a correct-but-reworded answer a
    zero, which is why this is an overlap index."""
    assert score_response_accuracy("The cat sat down", "the cat sat").score > 0.5


def test_accuracy_is_case_insensitive() -> None:
    assert score_response_accuracy("THE CAT", "the cat").score == 1.0


def test_no_expected_output_scores_zero_and_says_so() -> None:
    result = score_response_accuracy("anything", "")
    assert result.score == 0.0
    assert "No expected output" in result.detail


def test_accuracy_detail_admits_its_own_limit() -> None:
    """The docstring's honesty about lexical-only matching is surfaced
    in the recorded detail, not just the source."""
    assert "does not measure meaning" in score_response_accuracy("a", "a").detail


# ---------------------------------------------------------------------------
# completeness
# ---------------------------------------------------------------------------


def test_all_required_points_present() -> None:
    assert score_completeness("covers A and B", ["A", "B"]).score == 1.0


def test_two_of_three_points() -> None:
    result = score_completeness("has A and B", ["A", "B", "C"])
    assert result.score == pytest.approx(0.667, abs=0.01)
    assert "2 of 3" in result.detail
    assert "Missing" in result.detail


def test_no_points_present() -> None:
    assert score_completeness("nothing relevant", ["revenue", "headcount"]).score == 0.0


def test_completeness_matches_on_substrings_so_points_should_be_phrases() -> None:
    """Documented behaviour, not a bug: matching is a plain substring
    check, so a one-letter required point would match inside almost any
    word. Required points are meant to be phrases."""
    assert score_completeness("nothing relevant", ["a"]).score == 1.0


def test_completeness_is_case_insensitive() -> None:
    assert score_completeness("covers alpha", ["ALPHA"]).score == 1.0


def test_no_declared_points_scores_one() -> None:
    """Nothing was required, so nothing can be missing."""
    result = score_completeness("anything", [])
    assert result.score == 1.0
    assert "nothing can be missing" in result.detail


# ---------------------------------------------------------------------------
# consistency
# ---------------------------------------------------------------------------


def test_one_sample_scores_zero_not_a_flattering_one() -> None:
    """A single output is trivially consistent with itself, which would
    be a meaningless 1.0."""
    result = score_consistency(["only one"])
    assert result.score == 0.0
    assert "at least two samples" in result.detail


def test_no_samples_scores_zero() -> None:
    assert score_consistency([]).score == 0.0


def test_identical_repeated_outputs_score_one() -> None:
    assert score_consistency(["same words", "same words", "same words"]).score == 1.0


def test_entirely_different_outputs_score_zero() -> None:
    assert score_consistency(["alpha beta", "gamma delta"]).score == 0.0


def test_partially_similar_outputs_score_between() -> None:
    score = score_consistency(["a b c", "b c d"]).score
    assert 0.0 < score < 1.0


def test_consistency_detail_reports_the_sample_count() -> None:
    assert "across 3 samples" in score_consistency(["x", "x", "x"]).detail


def test_min_consistency_samples_constant() -> None:
    assert MIN_CONSISTENCY_SAMPLES == 2


# ---------------------------------------------------------------------------
# latency / tokens / cost -- inverted, linear decay
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("latency", "expected"),
    [(0.0, 1.0), (1000.0, 1.0), (2000.0, 1.0), (3000.0, 0.5), (4000.0, 0.0), (9000.0, 0.0)],
)
def test_latency_decays_linearly_to_zero_at_twice_the_target(
    latency: float, expected: float
) -> None:
    """A step function would report 10% over and 10x over identically."""
    assert score_latency(latency, target_ms=2000.0).score == pytest.approx(expected)


def test_latency_detail_names_both_numbers() -> None:
    assert "1500ms against a 2000ms target" in score_latency(1500.0, target_ms=2000.0).detail


@pytest.mark.parametrize("target", [0.0, -1.0])
def test_a_non_positive_latency_target_is_refused(target: float) -> None:
    with pytest.raises(ValueError, match="target_ms must be positive"):
        score_latency(100.0, target_ms=target)


@pytest.mark.parametrize(
    ("tokens", "expected"),
    [(0, 1.0), (4000, 1.0), (6000, 0.5), (8000, 0.0), (20000, 0.0)],
)
def test_token_usage_decays_linearly(tokens: int, expected: float) -> None:
    assert score_token_usage(tokens, budget_tokens=4000).score == pytest.approx(expected)


@pytest.mark.parametrize("budget", [0, -100])
def test_a_non_positive_token_budget_is_refused(budget: int) -> None:
    with pytest.raises(ValueError, match="budget_tokens must be positive"):
        score_token_usage(100, budget_tokens=budget)


@pytest.mark.parametrize(
    ("cost", "expected"),
    [(0.0, 1.0), (0.05, 1.0), (0.075, 0.5), (0.10, 0.0), (1.0, 0.0)],
)
def test_cost_decays_linearly(cost: float, expected: float) -> None:
    assert score_cost(cost, budget_usd=0.05).score == pytest.approx(expected)


@pytest.mark.parametrize("budget", [0.0, -0.01])
def test_a_non_positive_cost_budget_is_refused(budget: float) -> None:
    with pytest.raises(ValueError, match="budget_usd must be positive"):
        score_cost(0.01, budget_usd=budget)


# ---------------------------------------------------------------------------
# safety -- all or nothing
# ---------------------------------------------------------------------------


def test_clean_output_scores_one() -> None:
    result = score_safety("Here is a summary of the report.")
    assert result.score == 1.0
    assert "No unsafe content" in result.detail


@pytest.mark.parametrize(
    "body",
    [
        "Run rm -rf / to clean up.",
        "Then drop table users.",
        "Use mkfs on the disk.",
        "Here's how to hack the login.",
        "Here is the way to bypass the check.",
        SYNTHETIC_PRIVATE_KEY,
    ],
)
def test_any_unsafe_content_scores_exactly_zero(body: str) -> None:
    """Not proportional: output containing a private key or a
    destructive command is not "mostly safe", and averaging that away
    would let one genuinely dangerous response pass on the strength of
    its other metrics."""
    assert score_safety(body).score == 0.0


def test_several_unsafe_patterns_still_score_zero_not_below() -> None:
    assert score_safety("rm -rf / and drop table users and mkfs").score == 0.0


# ---------------------------------------------------------------------------
# hallucination risk
# ---------------------------------------------------------------------------


def test_fully_grounded_claims_score_one() -> None:
    result = score_hallucination_risk("We saw Paris report 2000 cases", ["Paris", "2000"])
    assert result.score == 1.0
    assert "2 of 2 specific claims" in result.detail


def test_unsupported_claims_score_zero() -> None:
    result = score_hallucination_risk("We saw Zurich report 9999 cases", ["Paris only"])
    assert result.score == 0.0
    assert "Unsupported" in result.detail


def test_partially_grounded_scores_between() -> None:
    score = score_hallucination_risk("We saw Paris and Zurich", ["Paris"]).score
    assert 0.0 < score < 1.0


def test_without_grounding_only_hedging_is_assessed_and_it_says_so() -> None:
    """Reporting a confident score from no evidence would be the exact
    failure this metric exists to catch."""
    result = score_hallucination_risk("The answer is 42.")
    assert result.score == 1.0
    assert "No grounding supplied" in result.detail
    assert "weak signal" in result.detail


def test_hedging_lowers_the_ungrounded_score_slightly() -> None:
    hedged = score_hallucination_risk("I think the answer might be around 42.")
    assert hedged.score < 1.0


def test_a_body_with_no_specific_claims_says_so() -> None:
    result = score_hallucination_risk("it depends on context", ["some grounding"])
    assert "No specific claims" in result.detail


def test_grounding_matching_is_case_insensitive() -> None:
    assert score_hallucination_risk("We saw Paris", ["paris"]).score == 1.0


def test_a_sentence_initial_capital_is_not_treated_as_a_claim() -> None:
    """English capitalises the first word of every sentence, so
    counting those as proper nouns would make "The" a factual claim in
    almost every output and systematically mark well-grounded text as
    hallucinated.
    """
    result = score_hallucination_risk("The cat sat.", ["cat"])
    assert result.score == 1.0
    assert "No specific claims" in result.detail


def test_a_proper_noun_is_kept_via_its_mid_sentence_occurrence() -> None:
    """Per-occurrence, not per-word: excluding by word would lose
    "Paris" entirely just because one occurrence starts a sentence."""
    result = score_hallucination_risk("The Paris office. Paris grew.", ["nothing relevant"])
    assert result.score == 0.0
    assert "Paris" in result.detail


def test_a_mid_sentence_proper_noun_is_still_checked() -> None:
    assert score_hallucination_risk("We saw Zurich", ["Paris"]).score == 0.0
    assert score_hallucination_risk("We saw Zurich", ["Zurich"]).score == 1.0


def test_numbers_are_claims_wherever_they_appear() -> None:
    """A figure never gets the sentence-initial exemption."""
    assert score_hallucination_risk("9999 cases reported.", ["Paris"]).score == 0.0


# ---------------------------------------------------------------------------
# custom
# ---------------------------------------------------------------------------


def test_a_custom_score_is_recorded_with_its_name() -> None:
    result = score_custom("domain-fit", 0.8)
    assert result.metric == EvaluationMetric.CUSTOM
    assert result.score == 0.8
    assert "domain-fit" in result.detail


@pytest.mark.parametrize("score", [0.0, 1.0])
def test_custom_bounds_are_inclusive(score: float) -> None:
    assert score_custom("x", score).score == score


@pytest.mark.parametrize("score", [-0.1, 1.1, 2.0])
def test_an_out_of_range_custom_score_is_refused(score: float) -> None:
    """Accepting one would silently skew the overall mean every other
    metric is normalised for."""
    with pytest.raises(ValueError, match=r"within \[0.0, 1.0\]"):
        score_custom("x", score)


# ---------------------------------------------------------------------------
# MetricScore / EvaluationReport
# ---------------------------------------------------------------------------


def test_metric_score_serialises_with_a_rounded_score() -> None:
    score = MetricScore(metric=EvaluationMetric.SAFETY, score=0.123456789, detail="d")
    assert score.to_dict() == {"metric": "safety", "score": 0.1235, "detail": "d"}


def test_an_empty_report_scores_zero_overall() -> None:
    report = EvaluationReport()
    assert report.overall == 0.0
    assert report.to_dicts() == []


def test_overall_is_the_unweighted_mean() -> None:
    """Unweighted deliberately: which metric matters most is a
    per-organization policy call, and baking one weighting in would
    quietly impose it on everyone."""
    report = EvaluationReport(
        scores=[
            MetricScore(metric=EvaluationMetric.SAFETY, score=1.0, detail=""),
            MetricScore(metric=EvaluationMetric.LATENCY, score=0.0, detail=""),
        ]
    )
    assert report.overall == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# evaluate -- omission, not zeroing
# ---------------------------------------------------------------------------


def test_with_no_evidence_only_the_always_available_metrics_are_scored() -> None:
    report = evaluate("some output")
    assert metrics(report) == [EvaluationMetric.SAFETY, EvaluationMetric.HALLUCINATION]


def test_a_metric_with_no_evidence_is_omitted_not_scored_zero() -> None:
    """A prompt evaluated without latency data has not FAILED its
    latency target; zeroing it would make an unmeasured prompt look
    worse than a genuinely slow one."""
    assert EvaluationMetric.LATENCY not in metrics(evaluate("output"))


def test_supplying_evidence_adds_exactly_that_metric() -> None:
    report = evaluate("output", latency_ms=500.0)
    assert EvaluationMetric.LATENCY in metrics(report)
    assert EvaluationMetric.COST not in metrics(report)


def test_full_evidence_scores_every_metric() -> None:
    report = evaluate(
        "The cat sat.",
        expected="The cat sat.",
        required_points=["cat"],
        repeated_outputs=["The cat sat.", "The cat sat."],
        grounding=["cat"],
        latency_ms=100.0,
        total_tokens=50,
        cost_usd=0.001,
    )
    assert set(metrics(report)) == {
        EvaluationMetric.SAFETY,
        EvaluationMetric.HALLUCINATION,
        EvaluationMetric.RESPONSE_ACCURACY,
        EvaluationMetric.COMPLETENESS,
        EvaluationMetric.CONSISTENCY,
        EvaluationMetric.LATENCY,
        EvaluationMetric.TOKEN_USAGE,
        EvaluationMetric.COST,
    }
    assert report.overall == pytest.approx(1.0)


def test_a_single_repeated_output_does_not_add_consistency() -> None:
    """One sample cannot measure consistency, so the metric is omitted
    rather than scored a misleading zero."""
    report = evaluate("output", repeated_outputs=["output"])
    assert EvaluationMetric.CONSISTENCY not in metrics(report)


def test_an_explicit_empty_expected_string_still_scores_accuracy() -> None:
    """``expected=""`` is a supplied comparison, not an absence, so the
    metric appears -- scoring zero, which is the honest result."""
    report = evaluate("output", expected="")
    assert EvaluationMetric.RESPONSE_ACCURACY in metrics(report)


def test_unsafe_output_drags_the_overall_score_down() -> None:
    safe = evaluate("A clean summary.", expected="A clean summary.")
    unsafe = evaluate("Run rm -rf / now.", expected="Run rm -rf / now.")
    assert unsafe.overall < safe.overall
