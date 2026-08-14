"""Integration tests for repository query methods, against real PostgreSQL."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from shared_core.exceptions.not_found import NotFoundError

from app.models.accounts import CloudAccount, CloudProject, CloudProvider, CloudRegion
from app.models.enums import (
    AuditAction,
    CloudComplianceFramework,
    CloudComplianceStatus,
    CloudPolicyStatus,
    CloudPolicyType,
    CloudProviderType,
    CloudResourceLifecycleState,
    CloudResourceType,
    DriftSeverity,
    DriftStatus,
    IaCDeploymentStatus,
    IaCTool,
    ReportFormat,
    ReportKind,
    ReportStatus,
)
from app.models.operations import (
    CloudBudget,
    CloudCatalogItem,
    CloudCompliance,
    CloudCost,
    CloudDrift,
    CloudIaC,
    CloudPolicy,
)
from app.models.reporting import CloudAudit, CloudReport, CloudStatistic
from app.models.resources import CloudCompute, CloudResource

NOW = datetime(2026, 6, 1, tzinfo=UTC)


def _provider(organization_id: UUID, *, name: str = "aws-prod") -> CloudProvider:
    return CloudProvider(
        organization_id=organization_id, provider_type=CloudProviderType.AWS, name=name
    )


def _account(organization_id: UUID, provider_id: UUID, *, name: str = "a1") -> CloudAccount:
    return CloudAccount(
        organization_id=organization_id,
        provider_id=provider_id,
        external_account_id="123456789",
        name=name,
        credential_ref="ref",
    )


def _resource(organization_id: UUID, account_id: UUID, *, name: str = "r1") -> CloudResource:
    return CloudResource(
        organization_id=organization_id,
        account_id=account_id,
        resource_type=CloudResourceType.VIRTUAL_MACHINE,
        external_id="i-123",
        name=name,
    )


class TestCloudProviderRepository:
    async def test_find_by_type(self, repos, organization_id: UUID) -> None:
        created = await repos.providers.create(_provider(organization_id))
        found = await repos.providers.find_by_type(
            organization_id, provider_type=CloudProviderType.AWS
        )
        assert found is not None and found.id == created.id

    async def test_list_enabled(self, repos, organization_id: UUID) -> None:
        await repos.providers.create(_provider(organization_id))
        found = await repos.providers.list_enabled(organization_id)
        assert len(found) == 1

    async def test_list_recent(self, repos, organization_id: UUID) -> None:
        await repos.providers.create(_provider(organization_id))
        found = await repos.providers.list_recent(organization_id)
        assert len(found) == 1


class TestCloudAccountRepository:
    async def test_require_in_org(self, repos, organization_id: UUID) -> None:
        provider = await repos.providers.create(_provider(organization_id))
        created = await repos.accounts.create(_account(organization_id, provider.id))
        found = await repos.accounts.require_in_org(organization_id, created.id)
        assert found.id == created.id

    async def test_require_in_org_missing_raises(self, repos, organization_id: UUID) -> None:
        with pytest.raises(NotFoundError):
            await repos.accounts.require_in_org(organization_id, uuid4())

    async def test_list_for_provider(self, repos, organization_id: UUID) -> None:
        provider = await repos.providers.create(_provider(organization_id))
        await repos.accounts.create(_account(organization_id, provider.id))
        found = await repos.accounts.list_for_provider(provider.id)
        assert len(found) == 1

    async def test_list_recent_and_organization_ids(self, repos, organization_id: UUID) -> None:
        provider = await repos.providers.create(_provider(organization_id))
        await repos.accounts.create(_account(organization_id, provider.id))
        found = await repos.accounts.list_recent(organization_id)
        assert len(found) == 1
        ids = await repos.accounts.list_organization_ids()
        assert organization_id in ids


class TestCloudRegionRepository:
    async def test_list_for_provider(self, repos, organization_id: UUID) -> None:
        provider = await repos.providers.create(_provider(organization_id))
        await repos.regions.create(
            CloudRegion(
                organization_id=organization_id,
                provider_id=provider.id,
                code="us-east-1",
                name="US East",
            )
        )
        found = await repos.regions.list_for_provider(provider.id)
        assert len(found) == 1


class TestCloudProjectRepository:
    async def test_list_for_account(self, repos, organization_id: UUID) -> None:
        provider = await repos.providers.create(_provider(organization_id))
        account = await repos.accounts.create(_account(organization_id, provider.id))
        await repos.projects.create(
            CloudProject(
                organization_id=organization_id,
                account_id=account.id,
                external_project_id="proj-1",
                name="Project 1",
            )
        )
        found = await repos.projects.list_for_account(account.id)
        assert len(found) == 1


class TestCloudResourceRepository:
    async def test_find_by_external_id(self, repos, organization_id: UUID) -> None:
        provider = await repos.providers.create(_provider(organization_id))
        account = await repos.accounts.create(_account(organization_id, provider.id))
        created = await repos.resources.create(_resource(organization_id, account.id))
        found = await repos.resources.find_by_external_id(account.id, external_id="i-123")
        assert found is not None and found.id == created.id

    async def test_require_in_org_missing_raises(self, repos, organization_id: UUID) -> None:
        with pytest.raises(NotFoundError):
            await repos.resources.require_in_org(organization_id, uuid4())

    async def test_list_recent_filters(self, repos, organization_id: UUID) -> None:
        provider = await repos.providers.create(_provider(organization_id))
        account = await repos.accounts.create(_account(organization_id, provider.id))
        r1 = _resource(organization_id, account.id, name="a")
        r1.lifecycle_state = CloudResourceLifecycleState.ACTIVE
        r2 = _resource(organization_id, account.id, name="b")
        r2.lifecycle_state = CloudResourceLifecycleState.FAILED
        await repos.resources.create(r1)
        await repos.resources.create(r2)
        found = await repos.resources.list_recent(
            organization_id, lifecycle_state=CloudResourceLifecycleState.ACTIVE
        )
        assert len(found) == 1
        found_by_type = await repos.resources.list_recent(
            organization_id, resource_type=CloudResourceType.VIRTUAL_MACHINE
        )
        assert len(found_by_type) == 2

    async def test_list_organization_ids(self, repos, organization_id: UUID) -> None:
        provider = await repos.providers.create(_provider(organization_id))
        account = await repos.accounts.create(_account(organization_id, provider.id))
        await repos.resources.create(_resource(organization_id, account.id))
        ids = await repos.resources.list_organization_ids()
        assert organization_id in ids


class TestCloudComputeRepository:
    async def test_find_for_resource_and_list_for_org(self, repos, organization_id: UUID) -> None:
        provider = await repos.providers.create(_provider(organization_id))
        account = await repos.accounts.create(_account(organization_id, provider.id))
        resource = await repos.resources.create(_resource(organization_id, account.id))
        await repos.compute.create(
            CloudCompute(
                organization_id=organization_id, resource_id=resource.id, instance_type="t3.micro"
            )
        )
        found = await repos.compute.find_for_resource(resource.id)
        assert found is not None
        for_org = await repos.compute.list_for_org(organization_id)
        assert len(for_org) == 1


class TestCloudCostRepository:
    async def test_list_for_account_and_total(self, repos, organization_id: UUID) -> None:
        provider = await repos.providers.create(_provider(organization_id))
        account = await repos.accounts.create(_account(organization_id, provider.id))
        await repos.costs.create(
            CloudCost(
                organization_id=organization_id,
                account_id=account.id,
                amount=10.0,
                cost_category="compute",
                period_start=NOW,
                period_end=NOW + timedelta(days=1),
            )
        )
        await repos.costs.create(
            CloudCost(
                organization_id=organization_id,
                account_id=account.id,
                amount=5.0,
                cost_category="storage",
                period_start=NOW,
                period_end=NOW + timedelta(days=1),
            )
        )
        found = await repos.costs.list_for_account(account.id, since=NOW - timedelta(hours=1))
        assert len(found) == 2
        total = await repos.costs.total_for_account(account.id, since=NOW - timedelta(hours=1))
        assert total == 15.0


class TestCloudBudgetRepository:
    async def test_list_recent_and_organization_ids(self, repos, organization_id: UUID) -> None:
        await repos.budgets.create(
            CloudBudget(
                organization_id=organization_id,
                name="Monthly",
                amount=1000.0,
                period_start=NOW,
                period_end=NOW + timedelta(days=30),
            )
        )
        found = await repos.budgets.list_recent(organization_id)
        assert len(found) == 1
        ids = await repos.budgets.list_organization_ids()
        assert organization_id in ids


class TestCloudPolicyRepository:
    async def test_list_active_filters_by_type(self, repos, organization_id: UUID) -> None:
        p1 = await repos.policies.create(
            CloudPolicy(
                organization_id=organization_id,
                name="tag-policy",
                policy_type=CloudPolicyType.TAG,
                status=CloudPolicyStatus.ACTIVE,
            )
        )
        await repos.policies.create(
            CloudPolicy(
                organization_id=organization_id,
                name="draft-policy",
                policy_type=CloudPolicyType.NAMING,
                status=CloudPolicyStatus.DRAFT,
            )
        )
        active = await repos.policies.list_active(organization_id)
        assert len(active) == 1
        assert active[0].id == p1.id
        by_type = await repos.policies.list_active(organization_id, policy_type=CloudPolicyType.TAG)
        assert len(by_type) == 1


class TestCloudComplianceRepository:
    async def test_latest_for_framework_and_list(self, repos, organization_id: UUID) -> None:
        provider = await repos.providers.create(_provider(organization_id))
        account = await repos.accounts.create(_account(organization_id, provider.id))
        await repos.compliance.create(
            CloudCompliance(
                organization_id=organization_id,
                account_id=account.id,
                framework=CloudComplianceFramework.CIS,
                status=CloudComplianceStatus.NON_COMPLIANT,
                assessed_at=NOW - timedelta(days=1),
            )
        )
        await repos.compliance.create(
            CloudCompliance(
                organization_id=organization_id,
                account_id=account.id,
                framework=CloudComplianceFramework.CIS,
                status=CloudComplianceStatus.COMPLIANT,
                assessed_at=NOW,
            )
        )
        latest = await repos.compliance.latest_for_framework(
            account.id, framework=CloudComplianceFramework.CIS
        )
        assert latest is not None and latest.status == CloudComplianceStatus.COMPLIANT
        for_account = await repos.compliance.list_for_account(account.id)
        assert len(for_account) == 2
        recent = await repos.compliance.list_recent(organization_id)
        assert len(recent) == 2
        recent_by_framework = await repos.compliance.list_recent(
            organization_id, framework=CloudComplianceFramework.CIS
        )
        assert len(recent_by_framework) == 2
        ids = await repos.compliance.list_organization_ids()
        assert organization_id in ids


class TestCloudDriftRepository:
    async def test_list_for_resource_and_detected(self, repos, organization_id: UUID) -> None:
        provider = await repos.providers.create(_provider(organization_id))
        account = await repos.accounts.create(_account(organization_id, provider.id))
        resource = await repos.resources.create(_resource(organization_id, account.id))
        await repos.drift.create(
            CloudDrift(
                organization_id=organization_id,
                resource_id=resource.id,
                severity=DriftSeverity.MEDIUM,
                status=DriftStatus.DETECTED,
                detected_at=NOW,
            )
        )
        for_resource = await repos.drift.list_for_resource(resource.id)
        assert len(for_resource) == 1
        detected = await repos.drift.list_detected(organization_id)
        assert len(detected) == 1
        ids = await repos.drift.list_organization_ids()
        assert organization_id in ids


class TestCloudIaCRepository:
    async def test_list_for_resource_and_by_status(self, repos, organization_id: UUID) -> None:
        provider = await repos.providers.create(_provider(organization_id))
        account = await repos.accounts.create(_account(organization_id, provider.id))
        resource = await repos.resources.create(_resource(organization_id, account.id))
        await repos.iac.create(
            CloudIaC(
                organization_id=organization_id,
                resource_id=resource.id,
                tool=IaCTool.TERRAFORM,
                status=IaCDeploymentStatus.PLANNED,
            )
        )
        for_resource = await repos.iac.list_for_resource(resource.id)
        assert len(for_resource) == 1
        by_status = await repos.iac.list_by_status(
            organization_id, status=IaCDeploymentStatus.PLANNED
        )
        assert len(by_status) == 1


class TestCloudCatalogRepository:
    async def test_list_approved_and_recent(self, repos, organization_id: UUID) -> None:
        from app.models.enums import CatalogItemStatus

        await repos.catalog.create(
            CloudCatalogItem(
                organization_id=organization_id,
                name="Standard VM",
                resource_type=CloudResourceType.VIRTUAL_MACHINE,
                status=CatalogItemStatus.APPROVED,
                version_label="1.0.0",
            )
        )
        approved = await repos.catalog.list_approved(organization_id)
        assert len(approved) == 1
        recent = await repos.catalog.list_recent(organization_id)
        assert len(recent) == 1


class TestCloudStatisticRepository:
    async def test_find_window_and_list_range(self, repos, organization_id: UUID) -> None:
        await repos.statistics.create(
            CloudStatistic(
                organization_id=organization_id,
                window_start=NOW,
                window_end=NOW + timedelta(hours=1),
            )
        )
        found = await repos.statistics.find_window(organization_id, window_start=NOW)
        assert found is not None
        in_range = await repos.statistics.list_range(
            organization_id, since=NOW - timedelta(hours=1)
        )
        assert len(in_range) == 1

    async def test_find_window_missing_returns_none(self, repos, organization_id: UUID) -> None:
        assert await repos.statistics.find_window(organization_id, window_start=NOW) is None


class TestCloudReportRepository:
    async def test_list_recent(self, repos, organization_id: UUID) -> None:
        await repos.reports.create(
            CloudReport(
                organization_id=organization_id,
                kind=ReportKind.COST,
                report_format=ReportFormat.JSON,
                title="Cost Report",
                status=ReportStatus.COMPLETED,
            )
        )
        recent = await repos.reports.list_recent(organization_id, status=ReportStatus.COMPLETED)
        assert len(recent) == 1
        by_kind = await repos.reports.list_recent(organization_id, kind=ReportKind.COST)
        assert len(by_kind) == 1


class TestCloudAuditRepository:
    async def test_list_recent_and_for_entity(self, repos, organization_id: UUID) -> None:
        entity_id = uuid4()
        await repos.audit.create(
            CloudAudit(
                organization_id=organization_id,
                action=AuditAction.ACCOUNT_REGISTERED,
                entity_type="cloud_account",
                entity_id=entity_id,
                occurred_at=NOW,
            )
        )
        found = await repos.audit.list_recent(organization_id, since=NOW - timedelta(hours=1))
        assert len(found) == 1
        for_entity = await repos.audit.list_for_entity("cloud_account", entity_id)
        assert len(for_entity) == 1

    async def test_list_recent_excludes_before_since(self, repos, organization_id: UUID) -> None:
        await repos.audit.create(
            CloudAudit(
                organization_id=organization_id,
                action=AuditAction.ACCOUNT_REGISTERED,
                entity_type="cloud_account",
                occurred_at=NOW - timedelta(days=10),
            )
        )
        found = await repos.audit.list_recent(organization_id, since=NOW - timedelta(hours=1))
        assert found == []
