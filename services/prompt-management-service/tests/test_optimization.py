"""Tests for :mod:`app.optimization.tokens` and
:mod:`app.optimization.engine`.

Pure modules. The token counts here are an ESTIMATOR's output, so the
assertions check its documented *properties* -- determinism, ordering,
and the way chars-per-token diverges between prose, code, and CJK --
rather than pinning numbers a real BPE tokenizer would disagree with
anyway.
"""

from __future__ import annotations

import pytest

from app.models.enums import OptimizationKind
from app.optimization.engine import (
    DEFAULT_MIN_SAVING_RATIO,
    OptimizationReport,
    Suggestion,
    analyse,
    compress_whitespace,
    find_duplicate_lines,
    remove_filler,
    suggest_chain_review,
    suggest_compression,
    suggest_deduplication,
    suggest_few_shot_review,
    suggest_instruction_refinement,
)
from app.optimization.tokens import (
    TokenEstimate,
    estimate,
    estimate_cost_usd,
    estimate_tokens,
)

# ---------------------------------------------------------------------------
# tokens
# ---------------------------------------------------------------------------


def test_empty_string_is_zero_tokens() -> None:
    assert estimate_tokens("") == 0


def test_estimation_is_deterministic() -> None:
    """A saving computed between two revisions is only comparable if
    the same text always estimates the same count."""
    text = "Summarize the quarterly report in three bullet points."
    assert estimate_tokens(text) == estimate_tokens(text)


def test_longer_text_estimates_more_tokens() -> None:
    assert estimate_tokens("one two three four five") > estimate_tokens("one two")


def test_a_single_word_is_at_least_one_token() -> None:
    assert estimate_tokens("a") >= 1


def test_punctuation_is_counted_separately_from_words() -> None:
    """BPE splits punctuation off; the estimator mirrors that."""
    assert estimate_tokens("hello, world!") > estimate_tokens("hello world")


def test_code_is_denser_than_prose() -> None:
    """Code has more punctuation per character, so fewer chars/token.

    This is exactly where the naive "four characters per token" rule
    goes wrong, and the reason this estimator exists.
    """
    prose = estimate("The quick brown fox jumps over the lazy dog.")
    code = estimate("def f(x):\n    return x*2")
    assert code.characters_per_token < prose.characters_per_token


def test_non_latin_script_is_denser_still() -> None:
    cjk = estimate("日本語のテキスト")
    prose = estimate("The quick brown fox jumps over the lazy dog.")
    assert cjk.characters_per_token < prose.characters_per_token


def test_prose_ratio_is_in_a_believable_band() -> None:
    """Real BPE lands near 4 chars/token for English prose."""
    ratio = estimate("The quick brown fox jumps over the lazy dog.").characters_per_token
    assert 3.0 < ratio < 6.0


def test_estimate_reports_characters_and_words() -> None:
    result = estimate("two words")
    assert isinstance(result, TokenEstimate)
    assert result.characters == 9
    assert result.words == 2


def test_characters_per_token_of_empty_text_is_zero_not_a_crash() -> None:
    assert estimate("").characters_per_token == 0.0


def test_estimate_cost_scales_linearly() -> None:
    assert estimate_cost_usd(1_000, usd_per_1k_tokens=0.002) == pytest.approx(0.002)
    assert estimate_cost_usd(2_500, usd_per_1k_tokens=0.002) == pytest.approx(0.005)


def test_zero_tokens_cost_nothing() -> None:
    assert estimate_cost_usd(0, usd_per_1k_tokens=0.002) == 0.0


def test_a_free_model_costs_nothing() -> None:
    assert estimate_cost_usd(10_000, usd_per_1k_tokens=0.0) == 0.0


def test_negative_rate_is_refused() -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        estimate_cost_usd(100, usd_per_1k_tokens=-0.001)


# ---------------------------------------------------------------------------
# compress_whitespace / remove_filler
# ---------------------------------------------------------------------------


def test_runs_of_spaces_collapse() -> None:
    assert compress_whitespace("a    b") == "a b"


def test_trailing_spaces_are_stripped_per_line() -> None:
    assert compress_whitespace("a   \nb   ") == "a\nb"


def test_a_single_blank_line_is_preserved() -> None:
    """Paragraph structure changes how a model reads a prompt, so one
    blank line is meaningful and must survive."""
    assert compress_whitespace("a\n\nb") == "a\n\nb"


def test_three_or_more_blank_lines_collapse_to_one() -> None:
    assert compress_whitespace("a\n\n\n\n\nb") == "a\n\nb"


def test_compression_is_idempotent() -> None:
    once = compress_whitespace("a    b\n\n\n\nc   ")
    assert compress_whitespace(once) == once


def test_filler_with_a_shorter_equivalent_is_substituted_not_deleted() -> None:
    """Deleting "in order to" outright would break the sentence."""
    assert remove_filler("In order to succeed, act.") == "to succeed, act."


def test_pure_padding_is_removed() -> None:
    assert remove_filler("Please note that you must act.") == "you must act."


def test_filler_matching_is_case_insensitive() -> None:
    assert "in order to" not in remove_filler("IN ORDER TO win").lower()


def test_text_with_no_filler_is_only_whitespace_normalised() -> None:
    assert remove_filler("Act now.") == "Act now."


# ---------------------------------------------------------------------------
# find_duplicate_lines
# ---------------------------------------------------------------------------


def test_duplicate_lines_are_reported_once_in_first_seen_order() -> None:
    body = "Do A.\nDo B.\nDo A.\nDo C.\nDo B.\nDo A."
    assert find_duplicate_lines(body) == ("Do A.", "Do B.")


def test_no_duplicates_yields_an_empty_tuple() -> None:
    assert find_duplicate_lines("Do A.\nDo B.\nDo C.") == ()


def test_single_character_lines_are_ignored_even_when_repeated() -> None:
    """A repeated bullet or stray character is not a duplicated
    instruction, so lines under two characters are skipped."""
    assert find_duplicate_lines("-\n-\n\n\nA\nA") == ()


def test_duplicates_are_matched_after_stripping() -> None:
    assert find_duplicate_lines("  Do A.  \nDo A.") == ("Do A.",)


# ---------------------------------------------------------------------------
# Suggestion
# ---------------------------------------------------------------------------


def test_token_saving_is_never_negative() -> None:
    """A suggestion that somehow grew the prompt reports zero saving,
    not a negative one that would flatter a rollup."""
    suggestion = Suggestion(
        kind=OptimizationKind.COMPRESSION,
        rationale="x",
        original_tokens=10,
        optimized_tokens=15,
    )
    assert suggestion.token_saving == 0


def test_saving_ratio_of_a_zero_token_original_is_zero() -> None:
    assert Suggestion(kind=OptimizationKind.TOKEN, rationale="x").saving_ratio == 0.0


def test_saving_ratio() -> None:
    suggestion = Suggestion(
        kind=OptimizationKind.COMPRESSION,
        rationale="x",
        original_tokens=100,
        optimized_tokens=75,
    )
    assert suggestion.token_saving == 25
    assert suggestion.saving_ratio == pytest.approx(0.25)


def test_a_suggestion_with_a_rewrite_is_not_advisory() -> None:
    assert (
        Suggestion(
            kind=OptimizationKind.COMPRESSION, rationale="x", suggested_body="shorter"
        ).is_advisory
        is False
    )


def test_a_suggestion_without_a_rewrite_is_advisory() -> None:
    assert Suggestion(kind=OptimizationKind.CHAIN, rationale="x").is_advisory is True


# ---------------------------------------------------------------------------
# individual suggesters
# ---------------------------------------------------------------------------


PADDED = "Please note that   you must  do X.\n\n\n\nIn order to succeed, do Y."


def test_compression_suggests_a_rewrite_when_the_saving_clears_the_floor() -> None:
    suggestion = suggest_compression(PADDED, min_saving_ratio=0.01)
    assert suggestion is not None
    assert suggestion.kind == OptimizationKind.COMPRESSION
    assert suggestion.suggested_body is not None
    assert suggestion.token_saving > 0


def test_compression_is_silent_on_an_already_tight_prompt() -> None:
    """A clean prompt must produce no noise."""
    assert suggest_compression("Summarize the text.") is None


def test_compression_is_silent_when_the_saving_is_below_the_floor() -> None:
    assert suggest_compression(PADDED, min_saving_ratio=0.99) is None


def test_deduplication_is_advisory_only() -> None:
    """A repeated line is sometimes deliberate emphasis, so this
    reports rather than rewrites."""
    suggestion = suggest_deduplication("Do X.\nDo Y.\nDo X.")
    assert suggestion is not None
    assert suggestion.is_advisory is True
    assert suggestion.token_saving == 0
    assert "more than once" in suggestion.rationale


def test_deduplication_is_silent_without_duplicates() -> None:
    assert suggest_deduplication("Do X.\nDo Y.") is None


def test_few_shot_review_fires_past_the_threshold() -> None:
    body = "\n".join(f"Example: case {index}" for index in range(8))
    suggestion = suggest_few_shot_review(body, max_examples=5)
    assert suggestion is not None
    assert suggestion.kind == OptimizationKind.FEW_SHOT
    assert suggestion.is_advisory is True


def test_few_shot_review_is_silent_at_or_below_the_threshold() -> None:
    body = "\n".join(f"Example: case {index}" for index in range(5))
    assert suggest_few_shot_review(body, max_examples=5) is None


def test_chain_review_fires_past_the_threshold() -> None:
    body = "\n".join(f"Step {index}: do it" for index in range(15))
    suggestion = suggest_chain_review(body, max_steps=12)
    assert suggestion is not None
    assert suggestion.kind == OptimizationKind.CHAIN
    assert suggestion.is_advisory is True


def test_chain_review_is_silent_below_the_threshold() -> None:
    assert suggest_chain_review("First do A. Then do B.", max_steps=12) is None


def test_instruction_refinement_fires_on_a_very_long_sentence() -> None:
    body = " ".join(["word"] * 80) + "."
    suggestion = suggest_instruction_refinement(body, max_sentence_words=60)
    assert suggestion is not None
    assert suggestion.kind == OptimizationKind.INSTRUCTION_REFINEMENT
    assert suggestion.is_advisory is True


def test_instruction_refinement_is_silent_on_short_sentences() -> None:
    assert suggest_instruction_refinement("Do X. Do Y.", max_sentence_words=60) is None


# ---------------------------------------------------------------------------
# analyse
# ---------------------------------------------------------------------------


def test_analyse_returns_a_report_with_the_original_count() -> None:
    report = analyse("Summarize the text.")
    assert isinstance(report, OptimizationReport)
    assert report.original_tokens == estimate_tokens("Summarize the text.")


def test_analyse_produces_no_suggestions_for_a_clean_prompt() -> None:
    """Noise is the failure mode that makes an advisory tool ignored."""
    assert analyse("Summarize the text.").suggestions == []


def test_analyse_finds_both_a_rewrite_and_an_advisory_finding() -> None:
    body = PADDED + "\nAlways cite sources.\nAlways cite sources."
    report = analyse(body, min_saving_ratio=0.01)
    kinds = {suggestion.kind for suggestion in report.suggestions}
    assert OptimizationKind.COMPRESSION in kinds
    assert OptimizationKind.TOKEN in kinds


def test_best_saving_picks_the_largest() -> None:
    report = analyse(PADDED, min_saving_ratio=0.01)
    assert report.best_saving == max(s.token_saving for s in report.suggestions)


def test_best_saving_of_an_empty_report_is_zero() -> None:
    assert OptimizationReport(original_tokens=10).best_saving == 0


def test_default_min_saving_ratio() -> None:
    assert DEFAULT_MIN_SAVING_RATIO == 0.05
