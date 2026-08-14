"""Tests for app.compliance.engine: score classification and
remediation scheduling."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.compliance.engine import (
    classify_compliance_status,
    compute_remediation_due_at,
    is_reassessment_due,
)
from app.models.enums import CloudComplianceStatus


class TestClassifyComplianceStatus:
    def test_none_is_not_assessed(self) -> None:
        result = classify_compliance_status(None, compliant_threshold=90, partial_threshold=60)
        assert result == CloudComplianceStatus.NOT_ASSESSED

    def test_high_score_is_compliant(self) -> None:
        result = classify_compliance_status(95, compliant_threshold=90, partial_threshold=60)
        assert result == CloudComplianceStatus.COMPLIANT

    def test_mid_score_is_partially_compliant(self) -> None:
        result = classify_compliance_status(70, compliant_threshold=90, partial_threshold=60)
        assert result == CloudComplianceStatus.PARTIALLY_COMPLIANT

    def test_low_score_is_non_compliant(self) -> None:
        result = classify_compliance_status(30, compliant_threshold=90, partial_threshold=60)
        assert result == CloudComplianceStatus.NON_COMPLIANT

    def test_out_of_range_score_raises(self) -> None:
        with pytest.raises(ValueError, match="within"):
            classify_compliance_status(150, compliant_threshold=90, partial_threshold=60)


class TestComputeRemediationDueAt:
    def test_adds_grace_days(self) -> None:
        assessed_at = datetime(2026, 1, 1, tzinfo=UTC)
        due = compute_remediation_due_at(assessed_at, grace_days=14)
        assert due == assessed_at + timedelta(days=14)

    def test_non_positive_grace_days_raises(self) -> None:
        with pytest.raises(ValueError, match="grace_days"):
            compute_remediation_due_at(datetime.now(UTC), grace_days=0)


class TestIsReassessmentDue:
    def test_never_assessed_is_due(self) -> None:
        assert is_reassessment_due(None, now=datetime.now(UTC), reassessment_days=30)

    def test_recent_assessment_not_due(self) -> None:
        now = datetime.now(UTC)
        assert not is_reassessment_due(now - timedelta(days=5), now=now, reassessment_days=30)

    def test_old_assessment_is_due(self) -> None:
        now = datetime.now(UTC)
        assert is_reassessment_due(now - timedelta(days=45), now=now, reassessment_days=30)
