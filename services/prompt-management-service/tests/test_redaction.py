"""Tests for :mod:`app.security.redaction`.

Pure module. The load-bearing assertion in this file is that
``detect()`` never returns the value it detected -- a finding that
quoted the secret would write it into the database, into every backup,
and into any log line rendering the row.
"""

from __future__ import annotations

import pytest

from app.security.redaction import (
    REDACTION_PLACEHOLDER,
    RedactionResult,
    detect,
    is_pii,
    mask_values,
    redact,
)

SYNTHETIC_PRIVATE_KEY = "-----BEGIN PRIVATE KEY-----\nMIIBVQ==\n-----END PRIVATE KEY-----"
"""Eight characters of base64 -- a shape, not usable key material."""


# ---------------------------------------------------------------------------
# The property this module exists for
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "secret"),
    [
        ("api_key = sk-live-abcdef123456", "sk-live-abcdef123456"),
        ("password: hunter2seventeen", "hunter2seventeen"),
        ("Authorization: Bearer abcdefghij0123456789", "abcdefghij0123456789"),
        ("postgres://user:s3cretpassword@db:5432/x", "s3cretpassword"),
    ],
)
def test_detect_never_returns_the_matched_secret(text: str, secret: str) -> None:
    """Only pattern *names* come back, never values."""
    assert secret not in str(detect(text))


def test_redaction_result_never_carries_the_secret_either() -> None:
    result = redact("api_key = sk-live-abcdef123456")
    assert "sk-live-abcdef123456" not in result.text
    assert "sk-live-abcdef123456" not in str(result.redacted_kinds)


# ---------------------------------------------------------------------------
# detect
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected_kind"),
    [
        (SYNTHETIC_PRIVATE_KEY, "private_key"),
        ("AKIAIOSFODNN7EXAMPLE", "aws_access_key"),
        ("ASIAIOSFODNN7EXAMPLE", "aws_access_key"),
        ("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NX0.dBjftJeZ4CVPmB92K2", "jwt"),
        ("postgres://user:pw123456@host:5432/db", "connection_string_password"),
        ("mongodb://user:pw123456@host/db", "connection_string_password"),
        ("api_key = abcdef123456", "assigned_secret"),
        ("SECRET: abcdef123456", "assigned_secret"),
        ("Bearer abcdefghij0123456789", "bearer_token"),
        ("write to ada@example.com", "email"),
        ("4111 1111 1111 1111", "credit_card"),
        ("host 192.168.1.10 replied", "ipv4"),
    ],
)
def test_detect_finds_each_pattern(text: str, expected_kind: str) -> None:
    assert expected_kind in detect(text)


def test_detect_returns_kinds_sorted_and_deduplicated() -> None:
    kinds = detect("mail a@b.com and c@d.com from 10.0.0.1")
    assert kinds == tuple(sorted(set(kinds)))
    assert kinds.count("email") == 1


def test_detect_finds_nothing_in_clean_text() -> None:
    assert detect("Summarize the quarterly report in three bullet points.") == ()


def test_detect_is_case_insensitive_for_assigned_secrets() -> None:
    assert "assigned_secret" in detect("API_KEY = abcdef123456")


def test_a_short_assignment_is_not_treated_as_a_secret() -> None:
    """The pattern requires at least six characters, so ``key = ab``
    does not fire -- a threshold that keeps ordinary prose out."""
    assert "assigned_secret" not in detect("api_key = ab")


# ---------------------------------------------------------------------------
# redact
# ---------------------------------------------------------------------------


def test_clean_text_is_returned_unchanged() -> None:
    text = "Summarize the report."
    result = redact(text)
    assert result.text == text
    assert result.redacted_kinds == ()
    assert result.was_redacted is False


def test_was_redacted_is_true_when_something_fired() -> None:
    assert redact("mail ada@example.com").was_redacted is True


def test_grouped_pattern_keeps_the_label_and_masks_only_the_value() -> None:
    """``api_key=[REDACTED]`` still tells a reader a key was there."""
    assert redact("api_key = abcdef123456").text == f"api_key = {REDACTION_PLACEHOLDER}"


def test_connection_string_keeps_its_shape() -> None:
    result = redact("postgres://user:pw123456@host:5432/db")
    assert result.text == f"postgres://user:{REDACTION_PLACEHOLDER}@host:5432/db"


def test_bearer_keeps_its_scheme() -> None:
    assert redact("Bearer abcdefghij0123456789").text == f"Bearer {REDACTION_PLACEHOLDER}"


def test_ungrouped_pattern_replaces_the_whole_match() -> None:
    assert redact("AKIAIOSFODNN7EXAMPLE").text == REDACTION_PLACEHOLDER


def test_surrounding_prose_survives_redaction() -> None:
    result = redact("Please email ada@example.com about the outage.")
    assert result.text == f"Please email {REDACTION_PLACEHOLDER} about the outage."


def test_multiple_kinds_are_all_reported_and_all_masked() -> None:
    result = redact("mail ada@example.com from 10.0.0.1")
    assert set(result.redacted_kinds) == {"email", "ipv4"}
    assert "ada@example.com" not in result.text
    assert "10.0.0.1" not in result.text


def test_redaction_is_idempotent() -> None:
    once = redact("api_key = abcdef123456").text
    assert redact(once).text == once


def test_private_key_block_is_removed_entirely() -> None:
    result = redact(f"before {SYNTHETIC_PRIVATE_KEY} after")
    assert "BEGIN PRIVATE KEY" not in result.text
    assert "private_key" in result.redacted_kinds


def test_redaction_result_shape() -> None:
    result = redact("mail ada@example.com")
    assert isinstance(result, RedactionResult)
    assert result.redacted_kinds == ("email",)


# ---------------------------------------------------------------------------
# is_pii
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["email", "credit_card", "ipv4"])
def test_pii_kinds(kind: str) -> None:
    assert is_pii(kind) is True


@pytest.mark.parametrize(
    "kind",
    ["private_key", "aws_access_key", "jwt", "assigned_secret", "bearer_token"],
)
def test_credential_kinds_are_not_pii(kind: str) -> None:
    """Graded separately so the scanner can block a credential while
    merely flagging an email address."""
    assert is_pii(kind) is False


def test_an_unknown_kind_is_not_pii() -> None:
    assert is_pii("something_else") is False


# ---------------------------------------------------------------------------
# mask_values
# ---------------------------------------------------------------------------


def test_mask_values_replaces_only_the_named_entries() -> None:
    masked = mask_values({"topic": "AI", "token": "s3cret"}, {"token"})
    assert masked == {"topic": "AI", "token": REDACTION_PLACEHOLDER}


def test_mask_values_with_nothing_to_mask_is_a_passthrough() -> None:
    values = {"a": 1, "b": "two"}
    assert mask_values(values, set()) == values


def test_mask_values_ignores_names_that_are_not_present() -> None:
    assert mask_values({"a": 1}, {"absent"}) == {"a": 1}


def test_mask_values_does_not_mutate_the_input() -> None:
    original = {"token": "s3cret"}
    mask_values(original, {"token"})
    assert original == {"token": "s3cret"}


def test_mask_values_masks_non_string_values_too() -> None:
    """A numeric secret is still a secret."""
    assert mask_values({"pin": 1234}, {"pin"}) == {"pin": REDACTION_PLACEHOLDER}
