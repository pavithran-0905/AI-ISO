"""Repository tests for :mod:`app.repositories.governance`.

Every query method is exercised against real PostgreSQL with both a row
that *should* match and a row that should *not*, so a filter that was
silently dropped fails here rather than in production.

Reviews, approvals, and scans all hang off a real
:class:`~app.models.prompt.PromptVersion` -- foreign keys are enforced,
so an invented UUID would be rejected rather than quietly stored.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

import pytest
from shared_core.exceptions.not_found import NotFoundError

from app.models.enums import (
    ApprovalStatus,
    PromptType,
    ReviewDecision,
    ScanStatus,
    SecurityFinding,
    SecuritySeverity,
)
from app.models.governance import PromptApproval, PromptReview, PromptSecurityScan
from app.models.prompt import Prompt, PromptVersion
from app.repositories.governance import (
    PromptApprovalRepository,
    PromptReviewRepository,
    PromptSecurityScanRepository,
)
from app.repositories.prompt import PromptRepository, PromptVersionRepository
from tests.conftest import ago, soon, utcnow


def one_minute() -> timedelta:
    return timedelta(minutes=1)


async def seed_prompt(
    repo: PromptRepository, organization_id: uuid.UUID, slug: str, **overrides: Any
) -> Prompt:
    fields: dict[str, Any] = {
        "organization_id": organization_id,
        "slug": slug,
        "name": slug.replace("-", " ").title(),
        "prompt_type": PromptType.SYSTEM,
    }
    fields.update(overrides)
    return await repo.create(Prompt(**fields))


async def seed_version(
    repo: PromptVersionRepository,
    organization_id: uuid.UUID,
    prompt_id: uuid.UUID,
    version_number: str = "1.0.0",
) -> PromptVersion:
    return await repo.create(
        PromptVersion(
            organization_id=organization_id,
            prompt_id=prompt_id,
            version_number=version_number,
            body=f"Body of {version_number}",
        )
    )


async def seed_review(
    repo: PromptReviewRepository,
    organization_id: uuid.UUID,
    prompt_version_id: uuid.UUID,
    reviewer_id: str,
    **overrides: Any,
) -> PromptReview:
    fields: dict[str, Any] = {
        "organization_id": organization_id,
        "prompt_version_id": prompt_version_id,
        "reviewer_id": reviewer_id,
    }
    fields.update(overrides)
    return await repo.create(PromptReview(**fields))


async def seed_approval(
    repo: PromptApprovalRepository,
    organization_id: uuid.UUID,
    prompt_version_id: uuid.UUID,
    **overrides: Any,
) -> PromptApproval:
    fields: dict[str, Any] = {
        "organization_id": organization_id,
        "prompt_version_id": prompt_version_id,
        "requested_at": utcnow(),
        "expires_at": soon(),
    }
    fields.update(overrides)
    return await repo.create(PromptApproval(**fields))


async def seed_scan(
    repo: PromptSecurityScanRepository,
    organization_id: uuid.UUID,
    prompt_version_id: uuid.UUID,
    **overrides: Any,
) -> PromptSecurityScan:
    fields: dict[str, Any] = {
        "organization_id": organization_id,
        "prompt_version_id": prompt_version_id,
        "scanned_at": utcnow(),
    }
    fields.update(overrides)
    return await repo.create(PromptSecurityScan(**fields))


# ---- PromptReviewRepository.require_in_org ----------------------------------


async def test_review_require_in_org_never_returns_another_tenants_row(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    reviews_repo: PromptReviewRepository,
    organization_id: uuid.UUID,
) -> None:
    other_org = uuid.uuid4()
    mine_version = await seed_version(
        versions_repo,
        organization_id,
        (await seed_prompt(prompts_repo, organization_id, "mine")).id,
    )
    theirs_version = await seed_version(
        versions_repo, other_org, (await seed_prompt(prompts_repo, other_org, "theirs")).id
    )
    mine = await seed_review(reviews_repo, organization_id, mine_version.id, "alice")
    theirs = await seed_review(reviews_repo, other_org, theirs_version.id, "alice")

    assert (await reviews_repo.require_in_org(organization_id, mine.id)).id == mine.id
    assert (await reviews_repo.require_in_org(other_org, theirs.id)).id == theirs.id

    with pytest.raises(NotFoundError):
        await reviews_repo.require_in_org(organization_id, theirs.id)
    with pytest.raises(NotFoundError):
        await reviews_repo.require_in_org(other_org, mine.id)
    with pytest.raises(NotFoundError):
        await reviews_repo.require_in_org(organization_id, uuid.uuid4())


# ---- PromptReviewRepository.list_for_version --------------------------------


async def test_review_list_for_version_is_newest_first_and_scoped_to_one_revision(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    reviews_repo: PromptReviewRepository,
    organization_id: uuid.UUID,
) -> None:
    prompt = await seed_prompt(prompts_repo, organization_id, "reviewed")
    version = await seed_version(versions_repo, organization_id, prompt.id, "1.0.0")
    sibling = await seed_version(versions_repo, organization_id, prompt.id, "1.1.0")

    oldest = await seed_review(
        reviews_repo, organization_id, version.id, "alice", created_at=ago(300)
    )
    middle = await seed_review(reviews_repo, organization_id, version.id, "bob", created_at=ago(200))
    newest = await seed_review(
        reviews_repo, organization_id, version.id, "carol", created_at=ago(100)
    )
    other = await seed_review(
        reviews_repo, organization_id, sibling.id, "dave", created_at=ago(150)
    )

    rows = await reviews_repo.list_for_version(version.id)
    assert [row.id for row in rows] == [newest.id, middle.id, oldest.id]
    assert other.id not in {row.id for row in rows}
    assert await reviews_repo.list_for_version(uuid.uuid4()) == []


# ---- PromptReviewRepository.has_unresolved_mandatory ------------------------


async def test_has_unresolved_mandatory_counts_pending_and_changes_requested(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    reviews_repo: PromptReviewRepository,
    organization_id: uuid.UUID,
) -> None:
    """A reviewer who asked for changes has not approved."""
    prompt = await seed_prompt(prompts_repo, organization_id, "mandatory")
    pending_version = await seed_version(versions_repo, organization_id, prompt.id, "1.0.0")
    changes_version = await seed_version(versions_repo, organization_id, prompt.id, "1.1.0")
    approved_version = await seed_version(versions_repo, organization_id, prompt.id, "1.2.0")

    await seed_review(
        reviews_repo,
        organization_id,
        pending_version.id,
        "alice",
        decision=ReviewDecision.PENDING,
        is_mandatory=True,
    )
    await seed_review(
        reviews_repo,
        organization_id,
        changes_version.id,
        "bob",
        decision=ReviewDecision.CHANGES_REQUESTED,
        is_mandatory=True,
    )
    await seed_review(
        reviews_repo,
        organization_id,
        approved_version.id,
        "carol",
        decision=ReviewDecision.APPROVED,
        is_mandatory=True,
    )

    assert await reviews_repo.has_unresolved_mandatory(pending_version.id) is True
    assert await reviews_repo.has_unresolved_mandatory(changes_version.id) is True
    assert await reviews_repo.has_unresolved_mandatory(approved_version.id) is False


async def test_has_unresolved_mandatory_ignores_advisory_reviews(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    reviews_repo: PromptReviewRepository,
    organization_id: uuid.UUID,
) -> None:
    prompt = await seed_prompt(prompts_repo, organization_id, "advisory")
    version = await seed_version(versions_repo, organization_id, prompt.id, "1.0.0")

    await seed_review(
        reviews_repo,
        organization_id,
        version.id,
        "alice",
        decision=ReviewDecision.PENDING,
        is_mandatory=False,
    )
    await seed_review(
        reviews_repo,
        organization_id,
        version.id,
        "bob",
        decision=ReviewDecision.CHANGES_REQUESTED,
        is_mandatory=False,
    )

    assert await reviews_repo.has_unresolved_mandatory(version.id) is False


async def test_has_unresolved_mandatory_treats_a_rejection_as_resolved(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    reviews_repo: PromptReviewRepository,
    organization_id: uuid.UUID,
) -> None:
    """``REJECTED`` is a decision that was reached, so this specific
    gate is satisfied -- the publish is still blocked, but by the
    approval count rather than by an outstanding review."""
    prompt = await seed_prompt(prompts_repo, organization_id, "rejected")
    version = await seed_version(versions_repo, organization_id, prompt.id, "1.0.0")
    await seed_review(
        reviews_repo,
        organization_id,
        version.id,
        "alice",
        decision=ReviewDecision.REJECTED,
        is_mandatory=True,
    )

    assert await reviews_repo.has_unresolved_mandatory(version.id) is False


async def test_has_unresolved_mandatory_is_false_for_a_revision_nobody_reviewed(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    reviews_repo: PromptReviewRepository,
    organization_id: uuid.UUID,
) -> None:
    prompt = await seed_prompt(prompts_repo, organization_id, "unreviewed")
    version = await seed_version(versions_repo, organization_id, prompt.id, "1.0.0")
    sibling = await seed_version(versions_repo, organization_id, prompt.id, "2.0.0")
    await seed_review(
        reviews_repo,
        organization_id,
        sibling.id,
        "alice",
        decision=ReviewDecision.PENDING,
        is_mandatory=True,
    )

    assert await reviews_repo.has_unresolved_mandatory(version.id) is False
    assert await reviews_repo.has_unresolved_mandatory(uuid.uuid4()) is False


# ---- PromptReviewRepository.count_by_decision -------------------------------


async def test_count_by_decision_groups_one_revisions_own_reviews(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    reviews_repo: PromptReviewRepository,
    organization_id: uuid.UUID,
) -> None:
    prompt = await seed_prompt(prompts_repo, organization_id, "counted")
    version = await seed_version(versions_repo, organization_id, prompt.id, "1.0.0")
    sibling = await seed_version(versions_repo, organization_id, prompt.id, "1.1.0")

    for reviewer in ("alice", "bob"):
        await seed_review(
            reviews_repo, organization_id, version.id, reviewer, decision=ReviewDecision.APPROVED
        )
    await seed_review(
        reviews_repo, organization_id, version.id, "carol", decision=ReviewDecision.REJECTED
    )
    await seed_review(
        reviews_repo, organization_id, sibling.id, "dave", decision=ReviewDecision.APPROVED
    )

    assert await reviews_repo.count_by_decision(version.id) == {"approved": 2, "rejected": 1}
    assert await reviews_repo.count_by_decision(uuid.uuid4()) == {}


# ---- PromptApprovalRepository.require_in_org --------------------------------


async def test_approval_require_in_org_never_returns_another_tenants_row(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    approvals_repo: PromptApprovalRepository,
    organization_id: uuid.UUID,
) -> None:
    other_org = uuid.uuid4()
    mine_version = await seed_version(
        versions_repo,
        organization_id,
        (await seed_prompt(prompts_repo, organization_id, "mine")).id,
    )
    theirs_version = await seed_version(
        versions_repo, other_org, (await seed_prompt(prompts_repo, other_org, "theirs")).id
    )
    mine = await seed_approval(approvals_repo, organization_id, mine_version.id)
    theirs = await seed_approval(approvals_repo, other_org, theirs_version.id)

    assert (await approvals_repo.require_in_org(organization_id, mine.id)).id == mine.id
    assert (await approvals_repo.require_in_org(other_org, theirs.id)).id == theirs.id

    with pytest.raises(NotFoundError):
        await approvals_repo.require_in_org(organization_id, theirs.id)
    with pytest.raises(NotFoundError):
        await approvals_repo.require_in_org(other_org, mine.id)
    with pytest.raises(NotFoundError):
        await approvals_repo.require_in_org(organization_id, uuid.uuid4())


# ---- PromptApprovalRepository.list_for_version ------------------------------


async def test_approval_list_for_version_is_oldest_request_first(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    approvals_repo: PromptApprovalRepository,
    organization_id: uuid.UUID,
) -> None:
    prompt = await seed_prompt(prompts_repo, organization_id, "approvals")
    version = await seed_version(versions_repo, organization_id, prompt.id, "1.0.0")
    sibling = await seed_version(versions_repo, organization_id, prompt.id, "1.1.0")

    second = await seed_approval(
        approvals_repo, organization_id, version.id, requested_at=ago(200)
    )
    first = await seed_approval(approvals_repo, organization_id, version.id, requested_at=ago(300))
    third = await seed_approval(approvals_repo, organization_id, version.id, requested_at=ago(100))
    other = await seed_approval(approvals_repo, organization_id, sibling.id, requested_at=ago(250))

    rows = await approvals_repo.list_for_version(version.id)
    assert [row.id for row in rows] == [first.id, second.id, third.id]
    assert other.id not in {row.id for row in rows}
    assert await approvals_repo.list_for_version(uuid.uuid4()) == []


# ---- PromptApprovalRepository.count_approved --------------------------------


async def test_count_approved_counts_distinct_approvers_not_rows(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    approvals_repo: PromptApprovalRepository,
    organization_id: uuid.UUID,
) -> None:
    """The same person approving twice must not satisfy a two-approver gate."""
    prompt = await seed_prompt(prompts_repo, organization_id, "double-approved")
    version = await seed_version(versions_repo, organization_id, prompt.id, "1.0.0")

    for _ in range(2):
        await seed_approval(
            approvals_repo,
            organization_id,
            version.id,
            approver_id="alice",
            status=ApprovalStatus.APPROVED,
        )

    assert len(await approvals_repo.list_for_version(version.id)) == 2
    assert await approvals_repo.count_approved(version.id) == 1

    await seed_approval(
        approvals_repo,
        organization_id,
        version.id,
        approver_id="bob",
        status=ApprovalStatus.APPROVED,
    )
    assert await approvals_repo.count_approved(version.id) == 2


async def test_count_approved_ignores_undecided_rejected_and_unattributed_rows(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    approvals_repo: PromptApprovalRepository,
    organization_id: uuid.UUID,
) -> None:
    prompt = await seed_prompt(prompts_repo, organization_id, "partly-approved")
    version = await seed_version(versions_repo, organization_id, prompt.id, "1.0.0")
    sibling = await seed_version(versions_repo, organization_id, prompt.id, "1.1.0")

    await seed_approval(
        approvals_repo,
        organization_id,
        version.id,
        approver_id="alice",
        status=ApprovalStatus.APPROVED,
    )
    await seed_approval(
        approvals_repo,
        organization_id,
        version.id,
        approver_id="bob",
        status=ApprovalStatus.PENDING,
    )
    await seed_approval(
        approvals_repo,
        organization_id,
        version.id,
        approver_id="carol",
        status=ApprovalStatus.REJECTED,
    )
    await seed_approval(
        approvals_repo,
        organization_id,
        version.id,
        approver_id="dave",
        status=ApprovalStatus.EXPIRED,
    )
    await seed_approval(
        approvals_repo,
        organization_id,
        version.id,
        approver_id=None,
        status=ApprovalStatus.APPROVED,
    )
    await seed_approval(
        approvals_repo,
        organization_id,
        sibling.id,
        approver_id="erin",
        status=ApprovalStatus.APPROVED,
    )

    assert await approvals_repo.count_approved(version.id) == 1
    assert await approvals_repo.count_approved(uuid.uuid4()) == 0


# ---- PromptApprovalRepository.list_pending_expired --------------------------


async def test_list_pending_expired_includes_exactly_at_the_cutoff(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    approvals_repo: PromptApprovalRepository,
    organization_id: uuid.UUID,
) -> None:
    prompt = await seed_prompt(prompts_repo, organization_id, "expiring")
    version = await seed_version(versions_repo, organization_id, prompt.id, "1.0.0")
    moment = utcnow()

    already = await seed_approval(
        approvals_repo,
        organization_id,
        version.id,
        status=ApprovalStatus.PENDING,
        expires_at=moment - one_minute(),
    )
    at_cutoff = await seed_approval(
        approvals_repo,
        organization_id,
        version.id,
        status=ApprovalStatus.PENDING,
        expires_at=moment,
    )
    later = await seed_approval(
        approvals_repo,
        organization_id,
        version.id,
        status=ApprovalStatus.PENDING,
        expires_at=moment + one_minute(),
    )
    decided = await seed_approval(
        approvals_repo,
        organization_id,
        version.id,
        status=ApprovalStatus.APPROVED,
        expires_at=moment - one_minute(),
    )

    lapsed = await approvals_repo.list_pending_expired(moment)
    assert [row.id for row in lapsed] == [already.id, at_cutoff.id]
    assert {later.id, decided.id}.isdisjoint({row.id for row in lapsed})

    assert [row.id for row in await approvals_repo.list_pending_expired(moment, limit=1)] == [
        already.id
    ]


async def test_list_pending_expired_is_empty_when_nothing_has_lapsed(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    approvals_repo: PromptApprovalRepository,
    organization_id: uuid.UUID,
) -> None:
    prompt = await seed_prompt(prompts_repo, organization_id, "fresh-request")
    version = await seed_version(versions_repo, organization_id, prompt.id, "1.0.0")
    await seed_approval(
        approvals_repo,
        organization_id,
        version.id,
        status=ApprovalStatus.PENDING,
        expires_at=soon(7_200),
    )

    assert await approvals_repo.list_pending_expired(utcnow()) == []


# ---- PromptApprovalRepository.list_pending_for_org --------------------------


async def test_list_pending_for_org_is_oldest_first_and_tenant_scoped(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    approvals_repo: PromptApprovalRepository,
    organization_id: uuid.UUID,
) -> None:
    other_org = uuid.uuid4()
    version = await seed_version(
        versions_repo,
        organization_id,
        (await seed_prompt(prompts_repo, organization_id, "queued")).id,
    )
    theirs_version = await seed_version(
        versions_repo, other_org, (await seed_prompt(prompts_repo, other_org, "theirs")).id
    )

    second = await seed_approval(
        approvals_repo,
        organization_id,
        version.id,
        status=ApprovalStatus.PENDING,
        requested_at=ago(200),
    )
    first = await seed_approval(
        approvals_repo,
        organization_id,
        version.id,
        status=ApprovalStatus.PENDING,
        requested_at=ago(300),
    )
    decided = await seed_approval(
        approvals_repo,
        organization_id,
        version.id,
        status=ApprovalStatus.APPROVED,
        requested_at=ago(400),
    )
    theirs = await seed_approval(
        approvals_repo,
        other_org,
        theirs_version.id,
        status=ApprovalStatus.PENDING,
        requested_at=ago(250),
    )

    rows = await approvals_repo.list_pending_for_org(organization_id)
    assert [row.id for row in rows] == [first.id, second.id]
    assert {decided.id, theirs.id}.isdisjoint({row.id for row in rows})

    assert [row.id for row in await approvals_repo.list_pending_for_org(organization_id, limit=1)] == [
        first.id
    ]
    assert await approvals_repo.list_pending_for_org(uuid.uuid4()) == []


# ---- PromptSecurityScanRepository.list_for_version / latest_for_version -----


async def test_scan_list_for_version_is_newest_first_and_scoped_to_one_revision(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    scans_repo: PromptSecurityScanRepository,
    organization_id: uuid.UUID,
) -> None:
    prompt = await seed_prompt(prompts_repo, organization_id, "scanned")
    version = await seed_version(versions_repo, organization_id, prompt.id, "1.0.0")
    sibling = await seed_version(versions_repo, organization_id, prompt.id, "1.1.0")

    oldest = await seed_scan(scans_repo, organization_id, version.id, scanned_at=ago(300))
    middle = await seed_scan(scans_repo, organization_id, version.id, scanned_at=ago(200))
    newest = await seed_scan(scans_repo, organization_id, version.id, scanned_at=ago(100))
    other = await seed_scan(scans_repo, organization_id, sibling.id, scanned_at=ago(50))

    rows = await scans_repo.list_for_version(version.id)
    assert [row.id for row in rows] == [newest.id, middle.id, oldest.id]
    assert other.id not in {row.id for row in rows}
    assert await scans_repo.list_for_version(uuid.uuid4()) == []


async def test_latest_for_version_returns_the_newest_scan_of_that_revision(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    scans_repo: PromptSecurityScanRepository,
    organization_id: uuid.UUID,
) -> None:
    prompt = await seed_prompt(prompts_repo, organization_id, "rescanned")
    version = await seed_version(versions_repo, organization_id, prompt.id, "1.0.0")
    sibling = await seed_version(versions_repo, organization_id, prompt.id, "1.1.0")

    await seed_scan(
        scans_repo,
        organization_id,
        version.id,
        scanned_at=ago(300),
        status=ScanStatus.BLOCKED,
        highest_severity=SecuritySeverity.CRITICAL,
    )
    newest = await seed_scan(
        scans_repo,
        organization_id,
        version.id,
        scanned_at=ago(100),
        status=ScanStatus.CLEAN,
        highest_severity=SecuritySeverity.INFO,
    )
    await seed_scan(scans_repo, organization_id, sibling.id, scanned_at=utcnow())

    latest = await scans_repo.latest_for_version(version.id)
    assert latest is not None
    assert latest.id == newest.id
    assert latest.status == ScanStatus.CLEAN
    assert await scans_repo.latest_for_version(uuid.uuid4()) is None


# ---- PromptSecurityScanRepository.list_blocking -----------------------------


async def test_list_blocking_returns_blocked_scans_only(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    scans_repo: PromptSecurityScanRepository,
    organization_id: uuid.UUID,
) -> None:
    """``FLAGGED`` raised a concern; only ``BLOCKED`` stops a publish."""
    other_org = uuid.uuid4()
    version = await seed_version(
        versions_repo,
        organization_id,
        (await seed_prompt(prompts_repo, organization_id, "blocking")).id,
    )
    theirs_version = await seed_version(
        versions_repo, other_org, (await seed_prompt(prompts_repo, other_org, "theirs")).id
    )

    newest_blocked = await seed_scan(
        scans_repo,
        organization_id,
        version.id,
        status=ScanStatus.BLOCKED,
        scanned_at=ago(100),
    )
    older_blocked = await seed_scan(
        scans_repo,
        organization_id,
        version.id,
        status=ScanStatus.BLOCKED,
        scanned_at=ago(300),
    )
    flagged = await seed_scan(
        scans_repo, organization_id, version.id, status=ScanStatus.FLAGGED, scanned_at=ago(200)
    )
    clean = await seed_scan(
        scans_repo, organization_id, version.id, status=ScanStatus.CLEAN, scanned_at=ago(50)
    )
    theirs = await seed_scan(
        scans_repo, other_org, theirs_version.id, status=ScanStatus.BLOCKED, scanned_at=ago(10)
    )

    rows = await scans_repo.list_blocking(organization_id)
    assert [row.id for row in rows] == [newest_blocked.id, older_blocked.id]
    assert {flagged.id, clean.id, theirs.id}.isdisjoint({row.id for row in rows})

    assert [row.id for row in await scans_repo.list_blocking(organization_id, limit=1)] == [
        newest_blocked.id
    ]
    assert await scans_repo.list_blocking(uuid.uuid4()) == []


# ---- PromptSecurityScanRepository.count_findings_in_window ------------------


async def test_count_findings_in_window_sums_only_in_window_rows(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    scans_repo: PromptSecurityScanRepository,
    organization_id: uuid.UUID,
) -> None:
    """Inclusive of ``since``, exclusive of ``until``."""
    other_org = uuid.uuid4()
    version = await seed_version(
        versions_repo,
        organization_id,
        (await seed_prompt(prompts_repo, organization_id, "findings")).id,
    )
    theirs_version = await seed_version(
        versions_repo, other_org, (await seed_prompt(prompts_repo, other_org, "theirs")).id
    )
    since = ago(3_600)
    until = ago(1_800)

    await seed_scan(scans_repo, organization_id, version.id, scanned_at=since, finding_count=2)
    await seed_scan(scans_repo, organization_id, version.id, scanned_at=ago(2_400), finding_count=3)
    await seed_scan(scans_repo, organization_id, version.id, scanned_at=until, finding_count=100)
    await seed_scan(scans_repo, organization_id, version.id, scanned_at=ago(7_200), finding_count=50)
    await seed_scan(scans_repo, other_org, theirs_version.id, scanned_at=ago(2_400), finding_count=9)

    assert (
        await scans_repo.count_findings_in_window(organization_id, since=since, until=until) == 5
    )
    assert (
        await scans_repo.count_findings_in_window(
            organization_id, since=ago(600), until=utcnow()
        )
        == 0
    )
    assert await scans_repo.count_findings_in_window(uuid.uuid4(), since=since, until=until) == 0


async def test_count_findings_in_window_reads_the_findings_written_alongside_the_count(
    prompts_repo: PromptRepository,
    versions_repo: PromptVersionRepository,
    scans_repo: PromptSecurityScanRepository,
    organization_id: uuid.UUID,
) -> None:
    version = await seed_version(
        versions_repo,
        organization_id,
        (await seed_prompt(prompts_repo, organization_id, "detailed")).id,
    )
    moment = utcnow()
    scan = await seed_scan(
        scans_repo,
        organization_id,
        version.id,
        scanned_at=moment,
        finding_count=1,
        highest_severity=SecuritySeverity.HIGH,
        status=ScanStatus.FLAGGED,
        findings=[
            {
                "finding": SecurityFinding.PROMPT_INJECTION,
                "severity": SecuritySeverity.HIGH,
                "description": "Instruction override attempt.",
            }
        ],
    )

    total = await scans_repo.count_findings_in_window(
        organization_id, since=moment, until=moment + one_minute()
    )
    assert total == 1
    assert scan.findings[0]["finding"] == SecurityFinding.PROMPT_INJECTION
    assert isinstance(scan.scanned_at, datetime)
