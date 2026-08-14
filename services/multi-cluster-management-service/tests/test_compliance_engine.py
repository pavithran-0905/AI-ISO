"""Tests for app.compliance.engine: score classification and remediation scheduling."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.compliance.engine import (
    classify_compliance_score,
    compute_remediation_due,
    is_reassessment_due,
)
from app.models.enums import ClusterComplianceStatus as Status

NOW = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)


class TestClassifyComplianceScore:
    def test_none_is_not_assessed(self) -> None:
        result = classify_compliance_score(None, compliant_threshold=95, partial_threshold=70)
        assert result is Status.NOT_ASSESSED

    def test_full_score_is_compliant(self) -> None:
        result = classify_compliance_score(100, compliant_threshold=95, partial_threshold=70)
        assert result is Status.COMPLIANT

    def test_at_compliant_threshold(self) -> None:
        result = classify_compliance_score(95, compliant_threshold=95, partial_threshold=70)
        assert result is Status.COMPLIANT

    def test_mid_score_is_partially_compliant(self) -> None:
        result = classify_compliance_score(80, compliant_threshold=95, partial_threshold=70)
        assert result is Status.PARTIALLY_COMPLIANT

    def test_low_score_is_non_compliant(self) -> None:
        result = classify_compliance_score(50, compliant_threshold=95, partial_threshold=70)
        assert result is Status.NON_COMPLIANT

    def test_invalid_threshold_ordering_raises(self) -> None:
        with pytest.raises(ValueError, match="must exceed"):
            classify_compliance_score(50, compliant_threshold=70, partial_threshold=70)

    def test_threshold_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError, match=r"\[0, 100\]"):
            classify_compliance_score(50, compliant_threshold=150, partial_threshold=70)


class TestComputeRemediationDue:
    def test_adds_grace_period(self) -> None:
        assert compute_remediation_due(NOW, grace_days=14) == NOW + timedelta(days=14)

    def test_zero_grace_days(self) -> None:
        assert compute_remediation_due(NOW, grace_days=0) == NOW

    def test_negative_grace_days_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            compute_remediation_due(NOW, grace_days=-1)


class TestIsReassessmentDue:
    def test_never_assessed_is_due(self) -> None:
        assert is_reassessment_due(None, now=NOW, reassessment_days=30)

    def test_recent_assessment_not_due(self) -> None:
        assert not is_reassessment_due(NOW - timedelta(days=10), now=NOW, reassessment_days=30)

    def test_old_assessment_is_due(self) -> None:
        assert is_reassessment_due(NOW - timedelta(days=31), now=NOW, reassessment_days=30)

    def test_exactly_at_boundary_is_due(self) -> None:
        assert is_reassessment_due(NOW - timedelta(days=30), now=NOW, reassessment_days=30)
