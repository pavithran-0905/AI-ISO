"""Governance service tests (:mod:`app.services.governance`).

Review, approval, security scanning, and the publication gate, all
against real PostgreSQL with a real recording publisher.

Two behaviours here are security properties rather than mere
correctness, and are asserted as such: **a scan never records the text
it matched** (neither in the persisted row nor on the event bus), and
**the gate collects every blocker** rather than short-circuiting, so a
second problem cannot hide behind the first one being fixed.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest
from shared_core.exceptions.conflict import ConflictError

from app.models.enums import (
    ApprovalStatus,
    AuditAction,
    PromptVersionStatus,
    ReviewDecision,
    ScanStatus,
    SecurityFinding,
    SecuritySeverity,
)
from app.models.governance import PromptApproval, PromptSecurityScan
from app.models.prompt import PromptVersion
from app.models.template import PromptVariable
from app.repositories.analytics import PromptAuditRepository
from app.repositories.governance import (
    PromptApprovalRepository,
    PromptReviewRepository,
    PromptSecurityScanRepository,
)
from app.repositories.template import PromptVariableRepository
from app.services.governance import (
    ApprovalService,
    GateResult,
    PublicationGate,
    ReviewService,
    SecurityService,
)
from tests.conftest import MakePromptFn, RecordingPublisher, ago, soon, utcnow

SECRET_BODY = "api_key = sk-live-abcdef123456"
"""A body carrying a credential the scanner detects as ``CRITICAL``.
The literal below is what must never appear in a scan row or an event."""

SECRET_TEXT = "sk-live-abcdef123456"


async def approve_by(
    service: ApprovalService,
    approvals: PromptApprovalRepository,
    version: PromptVersion,
    approver_id: str,
) -> PromptApproval:
    """Open and immediately grant one approval gate on *version*."""
    approval = await approvals.create(
        PromptApproval(
            organization_id=version.organization_id,
            prompt_version_id=version.id,
            status=ApprovalStatus.PENDING,
            requested_at=utcnow(),
            expires_at=soon(),
        )
    )
    return await service.decide(approval, approver_id=approver_id, approve=True)


# ---- ReviewService.request ---------------------------------------------------


async def test_request_opens_a_pending_review_for_one_reviewer(
    review_service: ReviewService, make_prompt: MakePromptFn
) -> None:
    _prompt, version = await make_prompt("greeting")

    review = await review_service.request(version, reviewer_id="reviewer-1", is_mandatory=True)

    assert review.prompt_version_id == version.id
    assert review.organization_id == version.organization_id
    assert review.reviewer_id == "reviewer-1"
    assert review.decision == ReviewDecision.PENDING
    assert review.is_mandatory is True
    assert review.submitted_at is None
    assert review.requested_changes == []


async def test_a_reviewer_cannot_hold_two_open_reviews_on_one_revision(
    review_service: ReviewService,
    reviews_repo: PromptReviewRepository,
    make_prompt: MakePromptFn,
) -> None:
    """Two open requests for one person would double-count their verdict."""
    _prompt, version = await make_prompt("greeting")
    await review_service.request(version, reviewer_id="reviewer-1")

    with pytest.raises(ConflictError, match="already has an open review"):
        await review_service.request(version, reviewer_id="reviewer-1")

    assert len(await reviews_repo.list_for_version(version.id)) == 1
    other = await review_service.request(version, reviewer_id="reviewer-2")
    assert other.reviewer_id == "reviewer-2"


async def test_a_reviewer_may_be_asked_again_once_their_first_review_is_decided(
    review_service: ReviewService, make_prompt: MakePromptFn
) -> None:
    _prompt, version = await make_prompt("greeting")
    first = await review_service.request(version, reviewer_id="reviewer-1")
    await review_service.submit(first, decision=ReviewDecision.CHANGES_REQUESTED)

    second = await review_service.request(version, reviewer_id="reviewer-1")
    assert second.id != first.id
    assert second.decision == ReviewDecision.PENDING


async def test_the_same_reviewer_may_hold_open_reviews_on_two_different_revisions(
    review_service: ReviewService, prompt_service: Any, make_prompt: MakePromptFn
) -> None:
    prompt, first = await make_prompt("greeting")
    second = await prompt_service.add_version(prompt, body="Hi {{ name }}")

    await review_service.request(first, reviewer_id="reviewer-1")
    on_second = await review_service.request(second, reviewer_id="reviewer-1")

    assert on_second.prompt_version_id == second.id


# ---- ReviewService.submit ----------------------------------------------------


async def test_submit_records_the_verdict_with_its_comments_and_changes(
    review_service: ReviewService, make_prompt: MakePromptFn
) -> None:
    _prompt, version = await make_prompt("greeting")
    review = await review_service.request(version, reviewer_id="reviewer-1")

    decided = await review_service.submit(
        review,
        decision=ReviewDecision.CHANGES_REQUESTED,
        comments="Tone is too casual.",
        requested_changes=["Drop the exclamation mark", "Name the product"],
    )

    assert decided.decision == ReviewDecision.CHANGES_REQUESTED
    assert decided.comments == "Tone is too casual."
    assert decided.requested_changes == ["Drop the exclamation mark", "Name the product"]
    assert decided.submitted_at is not None


async def test_a_decided_review_cannot_be_decided_again(
    review_service: ReviewService, make_prompt: MakePromptFn
) -> None:
    _prompt, version = await make_prompt("greeting")
    review = await review_service.request(version, reviewer_id="reviewer-1")
    await review_service.submit(review, decision=ReviewDecision.APPROVED)

    with pytest.raises(ConflictError, match="already decided"):
        await review_service.submit(review, decision=ReviewDecision.REJECTED)

    assert review.decision == ReviewDecision.APPROVED


async def test_pending_is_refused_as_a_verdict(
    review_service: ReviewService, make_prompt: MakePromptFn
) -> None:
    """Pending is the absence of a verdict, not one of them."""
    _prompt, version = await make_prompt("greeting")
    review = await review_service.request(version, reviewer_id="reviewer-1")

    with pytest.raises(ConflictError, match="PENDING is not a verdict"):
        await review_service.submit(review, decision=ReviewDecision.PENDING)

    assert review.decision == ReviewDecision.PENDING
    assert review.submitted_at is None


# ---- ReviewService.summarise -------------------------------------------------


async def test_summarise_counts_every_decision_and_flags_an_outstanding_mandatory(
    review_service: ReviewService, make_prompt: MakePromptFn
) -> None:
    _prompt, version = await make_prompt("greeting")
    approved = await review_service.request(version, reviewer_id="reviewer-1")
    await review_service.submit(approved, decision=ReviewDecision.APPROVED)
    rejected = await review_service.request(version, reviewer_id="reviewer-2")
    await review_service.submit(rejected, decision=ReviewDecision.REJECTED)
    changes = await review_service.request(version, reviewer_id="reviewer-3", is_mandatory=True)
    await review_service.submit(changes, decision=ReviewDecision.CHANGES_REQUESTED)
    await review_service.request(version, reviewer_id="reviewer-4")

    summary = await review_service.summarise(version.id)

    assert summary.approved == 1
    assert summary.rejected == 1
    assert summary.changes_requested == 1
    assert summary.pending == 1
    assert summary.mandatory_outstanding is True
    assert summary.by_decision == {
        str(ReviewDecision.APPROVED): 1,
        str(ReviewDecision.REJECTED): 1,
        str(ReviewDecision.CHANGES_REQUESTED): 1,
        str(ReviewDecision.PENDING): 1,
    }


async def test_summarise_of_a_revision_nobody_reviewed_is_all_zeroes(
    review_service: ReviewService, make_prompt: MakePromptFn
) -> None:
    _prompt, version = await make_prompt("greeting")

    summary = await review_service.summarise(version.id)

    assert (summary.approved, summary.rejected, summary.changes_requested, summary.pending) == (
        0,
        0,
        0,
        0,
    )
    assert summary.mandatory_outstanding is False
    assert summary.by_decision == {}


# ---- ApprovalService.request -------------------------------------------------


async def test_request_opens_a_gate_and_announces_it(
    approval_service: ApprovalService,
    publisher: RecordingPublisher,
    make_prompt: MakePromptFn,
) -> None:
    _prompt, version = await make_prompt("greeting")

    approval = await approval_service.request(
        version, required_approvals=2, expiry_seconds=3_600.0, requested_by="requester-1"
    )

    assert approval.prompt_version_id == version.id
    assert approval.status == ApprovalStatus.PENDING
    assert approval.required_approvals == 2
    assert approval.requested_by == "requester-1"
    assert approval.approver_id is None
    assert approval.decided_at is None
    assert (approval.expires_at - approval.requested_at).total_seconds() == pytest.approx(
        3_600.0, abs=1.0
    )

    assert publisher.names[-1] == "PromptApprovalRequested"
    assert publisher.events[-1].payload == {
        "prompt_version_id": str(version.id),
        "version_number": "1.0.0",
        "required_approvals": 2,
    }


@pytest.mark.parametrize("required", [0, -1])
async def test_request_refuses_a_non_positive_approval_requirement(
    approval_service: ApprovalService,
    approvals_repo: PromptApprovalRepository,
    make_prompt: MakePromptFn,
    required: int,
) -> None:
    _prompt, version = await make_prompt("greeting")

    with pytest.raises(ValueError, match="at least 1"):
        await approval_service.request(version, required_approvals=required)

    assert await approvals_repo.list_for_version(version.id) == []


# ---- ApprovalService.decide --------------------------------------------------


@pytest.mark.parametrize(
    ("approve", "expected_status"),
    [(True, ApprovalStatus.APPROVED), (False, ApprovalStatus.REJECTED)],
)
async def test_decide_records_the_verdict_and_writes_an_audit_row(
    approval_service: ApprovalService,
    audit_repo: PromptAuditRepository,
    make_prompt: MakePromptFn,
    organization_id: uuid.UUID,
    approve: bool,
    expected_status: ApprovalStatus,
) -> None:
    _prompt, version = await make_prompt("greeting")
    approval = await approval_service.request(version)

    decided = await approval_service.decide(
        approval, approver_id="approver-1", approve=approve, reason="Looks right."
    )

    assert decided.status == expected_status
    assert decided.approver_id == "approver-1"
    assert decided.reason == "Looks right."
    assert decided.decided_at is not None

    rows = [
        row
        for row in await audit_repo.list_for_org(organization_id)
        if row.action == AuditAction.APPROVAL_DECIDED
    ]
    assert len(rows) == 1
    assert rows[0].entity_type == "prompt_version"
    assert rows[0].entity_id == version.id
    assert rows[0].actor_id == "approver-1"
    assert rows[0].succeeded is approve


async def test_an_expired_approval_cannot_be_decided_late(
    approval_service: ApprovalService, make_prompt: MakePromptFn
) -> None:
    """Silently accepting a late decision would make the expiry meaningless."""
    _prompt, version = await make_prompt("greeting")
    approval = await approval_service.request(version, expiry_seconds=3_600.0)

    assert await approval_service.expire_lapsed(soon(7_200)) == 1
    assert approval.status == ApprovalStatus.EXPIRED

    with pytest.raises(ConflictError, match="not pending"):
        await approval_service.decide(approval, approver_id="approver-1", approve=True)

    assert approval.status == ApprovalStatus.EXPIRED
    assert approval.approver_id is None


async def test_an_already_decided_approval_cannot_be_decided_again(
    approval_service: ApprovalService, make_prompt: MakePromptFn
) -> None:
    _prompt, version = await make_prompt("greeting")
    approval = await approval_service.request(version)
    await approval_service.decide(approval, approver_id="approver-1", approve=True)

    with pytest.raises(ConflictError, match="not pending"):
        await approval_service.decide(approval, approver_id="approver-2", approve=False)

    assert approval.status == ApprovalStatus.APPROVED
    assert approval.approver_id == "approver-1"


# ---- ApprovalService.expire_lapsed -------------------------------------------


async def test_expire_lapsed_touches_only_pending_requests_past_their_deadline(
    approval_service: ApprovalService,
    approvals_repo: PromptApprovalRepository,
    make_prompt: MakePromptFn,
) -> None:
    _prompt, version = await make_prompt("greeting")
    lapsed = await approval_service.request(version, expiry_seconds=-60.0)
    still_open = await approval_service.request(version, expiry_seconds=3_600.0)
    already_decided = await approval_service.request(version, expiry_seconds=-60.0)
    await approval_service.decide(already_decided, approver_id="approver-1", approve=True)

    moment = utcnow()
    assert await approval_service.expire_lapsed(moment) == 1

    assert lapsed.status == ApprovalStatus.EXPIRED
    assert lapsed.decided_at == moment
    assert still_open.status == ApprovalStatus.PENDING
    assert already_decided.status == ApprovalStatus.APPROVED
    assert len(await approvals_repo.list_for_version(version.id)) == 3


async def test_expire_lapsed_reports_zero_when_nothing_has_lapsed(
    approval_service: ApprovalService, make_prompt: MakePromptFn
) -> None:
    _prompt, version = await make_prompt("greeting")
    await approval_service.request(version, expiry_seconds=3_600.0)

    assert await approval_service.expire_lapsed(ago(60)) == 0


# ---- distinct-approver counting ----------------------------------------------


async def test_one_person_approving_twice_does_not_satisfy_a_two_approver_gate(
    approval_service: ApprovalService,
    approvals_repo: PromptApprovalRepository,
    make_prompt: MakePromptFn,
) -> None:
    """Counting rows rather than people is the entire failure this guards."""
    _prompt, version = await make_prompt("greeting")

    await approve_by(approval_service, approvals_repo, version, "alice")
    await approve_by(approval_service, approvals_repo, version, "alice")

    assert await approvals_repo.count_approved(version.id) == 1
    assert await approval_service.is_satisfied(version, required=1) is True
    assert await approval_service.is_satisfied(version, required=2) is False


async def test_two_distinct_approvers_do_satisfy_a_two_approver_gate(
    approval_service: ApprovalService,
    approvals_repo: PromptApprovalRepository,
    make_prompt: MakePromptFn,
) -> None:
    _prompt, version = await make_prompt("greeting")

    await approve_by(approval_service, approvals_repo, version, "alice")
    await approve_by(approval_service, approvals_repo, version, "bob")

    assert await approvals_repo.count_approved(version.id) == 2
    assert await approval_service.is_satisfied(version, required=2) is True


async def test_a_rejection_never_counts_towards_the_gate(
    approval_service: ApprovalService,
    approvals_repo: PromptApprovalRepository,
    make_prompt: MakePromptFn,
) -> None:
    _prompt, version = await make_prompt("greeting")
    approval = await approval_service.request(version)
    await approval_service.decide(approval, approver_id="alice", approve=False)

    assert await approvals_repo.count_approved(version.id) == 0
    assert await approval_service.is_satisfied(version, required=1) is False


# ---- SecurityService ---------------------------------------------------------


async def test_a_clean_scan_records_nothing_and_announces_nothing(
    security_service: SecurityService,
    scans_repo: PromptSecurityScanRepository,
    publisher: RecordingPublisher,
    make_prompt: MakePromptFn,
) -> None:
    _prompt, version = await make_prompt("greeting", body="Summarise the change request.")

    scan = await security_service.scan_version(version, scanned_by="scanner-1")

    assert scan.status == ScanStatus.CLEAN
    assert scan.highest_severity == SecuritySeverity.INFO
    assert scan.findings == []
    assert scan.finding_count == 0
    assert scan.blocked_publish is False
    assert scan.scanned_by == "scanner-1"
    assert scan.prompt_version_id == version.id
    assert await scans_repo.latest_for_version(version.id) is not None
    assert "PromptSecurityViolation" not in publisher.names


async def test_a_critical_secret_blocks_and_neither_the_row_nor_the_event_quotes_it(
    security_service: SecurityService,
    scans_repo: PromptSecurityScanRepository,
    publisher: RecordingPublisher,
    make_prompt: MakePromptFn,
) -> None:
    """The security property this whole module exists for.

    A scan row that quoted the secret it found would put that secret in
    the database, in every backup of it, and in any log line rendering
    the row -- and an event payload carrying it would hand it to every
    subscriber's own logs as well.
    """
    _prompt, version = await make_prompt("leaky", body=SECRET_BODY)

    scan = await security_service.scan_version(version)

    assert scan.status == ScanStatus.BLOCKED
    assert scan.highest_severity == SecuritySeverity.CRITICAL
    assert scan.finding_count == 1
    assert scan.blocked_publish is True
    assert scan.findings[0]["finding"] == str(SecurityFinding.SECRET_DETECTED)
    assert scan.findings[0]["severity"] == str(SecuritySeverity.CRITICAL)

    assert SECRET_TEXT not in json.dumps(scan.findings)
    persisted = await scans_repo.latest_for_version(version.id)
    assert persisted is not None
    assert SECRET_TEXT not in json.dumps(persisted.findings)

    assert publisher.names[-1] == "PromptSecurityViolation"
    payload = publisher.events[-1].payload
    assert payload["prompt_version_id"] == str(version.id)
    assert payload["status"] == str(ScanStatus.BLOCKED)
    assert payload["highest_severity"] == str(SecuritySeverity.CRITICAL)
    assert payload["finding_count"] == 1
    assert payload["findings"] == [str(SecurityFinding.SECRET_DETECTED)]
    assert SECRET_TEXT not in json.dumps(payload)


async def test_block_on_critical_false_records_the_finding_without_blocking(
    security_service: SecurityService, make_prompt: MakePromptFn
) -> None:
    _prompt, version = await make_prompt("leaky", body=SECRET_BODY)

    scan = await security_service.scan_version(version, block_on_critical=False)

    assert scan.status == ScanStatus.BLOCKED
    assert scan.blocked_publish is False


async def test_the_undeclared_variable_check_reads_the_declarations_from_the_database(
    security_service: SecurityService,
    variables_repo: PromptVariableRepository,
    make_prompt: MakePromptFn,
) -> None:
    """A caller supplying its own list could suppress the finding, so the
    scanner never takes one."""
    _prompt, version = await make_prompt("greeting", body="Hello {{ name }}")

    flagged = await security_service.scan_version(version)
    assert flagged.status == ScanStatus.FLAGGED
    assert flagged.highest_severity == SecuritySeverity.HIGH
    assert flagged.findings[0]["finding"] == str(SecurityFinding.UNDECLARED_VARIABLE)

    await variables_repo.create(
        PromptVariable(
            organization_id=version.organization_id,
            prompt_version_id=version.id,
            name="name",
        )
    )
    clean = await security_service.scan_version(version)
    assert clean.status == ScanStatus.CLEAN
    assert clean.finding_count == 0


async def test_restricted_keywords_are_passed_through_to_the_scan(
    security_service: SecurityService, make_prompt: MakePromptFn
) -> None:
    _prompt, version = await make_prompt("greeting", body="Never mention Acme in the reply.")

    scan = await security_service.scan_version(version, restricted_keywords=["acme"])

    assert scan.status == ScanStatus.FLAGGED
    assert scan.finding_count == 1
    assert scan.findings[0]["finding"] == str(SecurityFinding.RESTRICTED_KEYWORD)
    assert scan.findings[0]["severity"] == str(SecuritySeverity.HIGH)


# ---- PublicationGate ---------------------------------------------------------


async def test_an_untouched_revision_is_blocked_by_every_gate_at_once(
    publication_gate: PublicationGate, make_prompt: MakePromptFn
) -> None:
    """Every blocker is collected, never just the first.

    Someone preparing a publish wants the full list of what to fix, not
    one round trip per problem.
    """
    _prompt, version = await make_prompt("greeting")

    result = await publication_gate.evaluate(version, required_approvals=2)

    assert result.allowed is False
    assert result.blockers == (
        "0 of 2 required approvals have been granted.",
        "No security scan has been run against this revision.",
    )
    assert result.reason == (
        "0 of 2 required approvals have been granted. "
        "No security scan has been run against this revision."
    )


async def test_a_mandatory_review_asking_for_changes_still_blocks(
    publication_gate: PublicationGate,
    review_service: ReviewService,
    approval_service: ApprovalService,
    approvals_repo: PromptApprovalRepository,
    security_service: SecurityService,
    variables_repo: PromptVariableRepository,
    make_prompt: MakePromptFn,
) -> None:
    """A reviewer who asked for changes has not approved.

    Treating ``CHANGES_REQUESTED`` as resolved would let a revision
    publish straight over an open objection.
    """
    _prompt, version = await make_prompt("greeting")
    await variables_repo.create(
        PromptVariable(
            organization_id=version.organization_id, prompt_version_id=version.id, name="name"
        )
    )
    await security_service.scan_version(version)
    await approve_by(approval_service, approvals_repo, version, "alice")

    review = await review_service.request(version, reviewer_id="reviewer-1", is_mandatory=True)
    await review_service.submit(review, decision=ReviewDecision.CHANGES_REQUESTED)

    blocked = await publication_gate.evaluate(version)
    assert blocked.allowed is False
    assert blocked.blockers == ("A mandatory review is still outstanding.",)

    second = await review_service.request(version, reviewer_id="reviewer-1", is_mandatory=True)
    await review_service.submit(second, decision=ReviewDecision.APPROVED)
    assert (await publication_gate.evaluate(version)).allowed is False

    await review_service.submit(review, decision=ReviewDecision.APPROVED)


async def test_a_fully_satisfied_gate_opens_and_says_so(
    publication_gate: PublicationGate,
    review_service: ReviewService,
    approval_service: ApprovalService,
    approvals_repo: PromptApprovalRepository,
    security_service: SecurityService,
    variables_repo: PromptVariableRepository,
    make_prompt: MakePromptFn,
) -> None:
    _prompt, version = await make_prompt("greeting")
    await variables_repo.create(
        PromptVariable(
            organization_id=version.organization_id, prompt_version_id=version.id, name="name"
        )
    )
    await security_service.scan_version(version)
    review = await review_service.request(version, reviewer_id="reviewer-1", is_mandatory=True)
    await review_service.submit(review, decision=ReviewDecision.APPROVED)
    await approve_by(approval_service, approvals_repo, version, "alice")

    result = await publication_gate.evaluate(version)

    assert result.allowed is True
    assert result.blockers == ()
    assert result.reason == "All publication gates are satisfied."


async def test_a_critical_scan_re_closes_an_otherwise_open_gate(
    publication_gate: PublicationGate,
    approval_service: ApprovalService,
    approvals_repo: PromptApprovalRepository,
    security_service: SecurityService,
    scans_repo: PromptSecurityScanRepository,
    make_prompt: MakePromptFn,
) -> None:
    _prompt, version = await make_prompt("leaky", body="Summarise the change request.")
    await approve_by(approval_service, approvals_repo, version, "alice")
    await security_service.scan_version(version)
    assert (await publication_gate.evaluate(version)).allowed is True

    await scans_repo.create(
        PromptSecurityScan(
            organization_id=version.organization_id,
            prompt_version_id=version.id,
            status=ScanStatus.BLOCKED,
            highest_severity=SecuritySeverity.CRITICAL,
            findings=[{"finding": str(SecurityFinding.SECRET_DETECTED)}],
            finding_count=1,
            scanned_at=utcnow(),
            blocked_publish=True,
        )
    )

    result = await publication_gate.evaluate(version)
    assert result.allowed is False
    assert result.blockers == (
        "The latest security scan found 1 finding(s) including a critical one.",
    )


async def test_a_non_critical_scan_leaves_the_gate_open(
    publication_gate: PublicationGate,
    approval_service: ApprovalService,
    approvals_repo: PromptApprovalRepository,
    security_service: SecurityService,
    make_prompt: MakePromptFn,
) -> None:
    _prompt, version = await make_prompt("greeting", body="Hello {{ name }}")
    await approve_by(approval_service, approvals_repo, version, "alice")

    flagged = await security_service.scan_version(version)
    assert flagged.highest_severity == SecuritySeverity.HIGH

    assert (await publication_gate.evaluate(version)).allowed is True


async def test_the_scan_and_critical_gates_can_each_be_switched_off(
    publication_gate: PublicationGate,
    approval_service: ApprovalService,
    approvals_repo: PromptApprovalRepository,
    security_service: SecurityService,
    make_prompt: MakePromptFn,
) -> None:
    _prompt, version = await make_prompt("leaky", body=SECRET_BODY)
    await approve_by(approval_service, approvals_repo, version, "alice")

    assert (await publication_gate.evaluate(version, require_scan=False)).allowed is True

    await security_service.scan_version(version)
    assert (await publication_gate.evaluate(version)).allowed is False
    assert (await publication_gate.evaluate(version, block_on_critical=False)).allowed is True


async def test_the_gate_reads_the_latest_scan_not_the_first_one(
    publication_gate: PublicationGate,
    approval_service: ApprovalService,
    approvals_repo: PromptApprovalRepository,
    scans_repo: PromptSecurityScanRepository,
    make_prompt: MakePromptFn,
) -> None:
    _prompt, version = await make_prompt("greeting", body="Summarise the change request.")
    await approve_by(approval_service, approvals_repo, version, "alice")
    await scans_repo.create(
        PromptSecurityScan(
            organization_id=version.organization_id,
            prompt_version_id=version.id,
            status=ScanStatus.BLOCKED,
            highest_severity=SecuritySeverity.CRITICAL,
            finding_count=3,
            scanned_at=ago(3_600),
        )
    )
    await scans_repo.create(
        PromptSecurityScan(
            organization_id=version.organization_id,
            prompt_version_id=version.id,
            status=ScanStatus.CLEAN,
            highest_severity=SecuritySeverity.INFO,
            finding_count=0,
            scanned_at=utcnow(),
        )
    )

    assert (await publication_gate.evaluate(version)).allowed is True


async def test_the_gate_scopes_everything_to_the_revision_it_was_asked_about(
    publication_gate: PublicationGate,
    prompt_service: Any,
    approval_service: ApprovalService,
    approvals_repo: PromptApprovalRepository,
    security_service: SecurityService,
    make_prompt: MakePromptFn,
) -> None:
    """Approving 1.0.0 must not silently open the gate on 1.0.1."""
    prompt, first = await make_prompt("greeting", body="Summarise the change request.")
    await approve_by(approval_service, approvals_repo, first, "alice")
    await security_service.scan_version(first)
    assert (await publication_gate.evaluate(first)).allowed is True

    second = await prompt_service.add_version(prompt, body="Summarise the request briefly.")
    assert second.status == PromptVersionStatus.DRAFT

    result = await publication_gate.evaluate(second)
    assert result.allowed is False
    assert result.blockers == (
        "0 of 1 required approvals have been granted.",
        "No security scan has been run against this revision.",
    )


def test_gate_result_reason_reads_as_one_sentence_when_allowed() -> None:
    assert GateResult(allowed=True).reason == "All publication gates are satisfied."
    assert GateResult(allowed=False, blockers=("One.", "Two.")).reason == "One. Two."
