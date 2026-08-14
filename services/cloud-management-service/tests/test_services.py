"""Integration tests for the service layer, against real PostgreSQL."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.catalog.engine import TransitionRefusal as CatalogTransitionRefusal
from app.iac.engine import TransitionRefusal as IaCTransitionRefusal
from app.models.accounts import CloudAccount, CloudProvider
from app.models.enums import (
    AuditAction,
    BudgetPeriod,
    CatalogItemStatus,
    CloudComplianceFramework,
    CloudPolicyType,
    CloudProviderType,
    CloudResourceLifecycleState,
    CloudResourceType,
    DriftStatus,
    IaCDeploymentStatus,
    IaCTool,
)
from app.models.resources import CloudResource
from app.resources.engine import TransitionRefusal
from app.services.accounts import CloudAccountService, CredentialRefusedError
from app.services.audit import AuditService
from app.services.catalog import CloudCatalogService
from app.services.catalog import TransitionRefusedError as CatalogTransitionRefusedError
from app.services.compliance import CloudComplianceService
from app.services.drift import CloudDriftService
from app.services.finops import CloudBudgetService, CloudCostService
from app.services.governance import CloudPolicyService
from app.services.iac import CloudIaCService
from app.services.iac import TransitionRefusedError as IaCTransitionRefusedError
from app.services.providers import CloudProjectService, CloudProviderService, CloudRegionService
from app.services.reports import ReportService
from app.services.resource_details import (
    ComputeService,
    DatabaseService,
    KubernetesService,
    NetworkService,
    StorageService,
)
from app.services.resources import CloudResourceService, TransitionRefusedError
from app.services.statistics import StatisticsService

NOW = datetime(2026, 6, 1, tzinfo=UTC)


async def _provider(repos, organization_id: UUID, **kwargs: object) -> CloudProvider:
    defaults: dict[str, object] = {
        "organization_id": organization_id,
        "provider_type": CloudProviderType.AWS,
        "name": "aws-prod",
    }
    defaults.update(kwargs)
    return await repos.providers.create(CloudProvider(**defaults))


async def _account(
    repos, organization_id: UUID, provider_id: UUID, **kwargs: object
) -> CloudAccount:
    defaults: dict[str, object] = {
        "organization_id": organization_id,
        "provider_id": provider_id,
        "external_account_id": "123456789",
        "name": "a1",
        "credential_ref": "ref",
    }
    defaults.update(kwargs)
    return await repos.accounts.create(CloudAccount(**defaults))


async def _resource(
    repos, organization_id: UUID, account_id: UUID, **kwargs: object
) -> CloudResource:
    defaults: dict[str, object] = {
        "organization_id": organization_id,
        "account_id": account_id,
        "resource_type": CloudResourceType.VIRTUAL_MACHINE,
        "external_id": "i-123",
        "name": "r1",
    }
    defaults.update(kwargs)
    return await repos.resources.create(CloudResource(**defaults))


class TestAuditService:
    async def test_record_creates_entry(self, repos, organization_id: UUID) -> None:
        service = AuditService(repos.audit)
        entry = await service.record(
            organization_id,
            action=AuditAction.ADMINISTRATIVE,
            entity_type="cloud_account",
            entity_id=uuid4(),
            occurred_at=NOW,
            summary="test entry",
        )
        assert entry.id is not None

    async def test_record_defaults_details_to_empty_dict(
        self, repos, organization_id: UUID
    ) -> None:
        service = AuditService(repos.audit)
        entry = await service.record(
            organization_id,
            action=AuditAction.ADMINISTRATIVE,
            entity_type="cloud_account",
            entity_id=None,
            occurred_at=NOW,
        )
        assert entry.details == {}


class TestCloudProviderService:
    async def test_register_enable_disable(self, repos, organization_id: UUID) -> None:
        service = CloudProviderService(repos.providers)
        provider = await service.register_provider(
            organization_id, provider_type=CloudProviderType.AZURE, name="azure-prod"
        )
        assert provider.is_enabled
        disabled = await service.disable(provider)
        assert not disabled.is_enabled
        enabled = await service.enable(disabled)
        assert enabled.is_enabled


class TestCloudRegionService:
    async def test_register_region(self, repos, organization_id: UUID) -> None:
        provider = await _provider(repos, organization_id)
        service = CloudRegionService(repos.regions)
        region = await service.register_region(
            organization_id, provider_id=provider.id, code="us-east-1", name="US East"
        )
        assert region.code == "us-east-1"


class TestCloudProjectService:
    async def test_register_project(self, repos, organization_id: UUID) -> None:
        provider = await _provider(repos, organization_id)
        account = await _account(repos, organization_id, provider.id)
        service = CloudProjectService(repos.projects)
        project = await service.register_project(
            organization_id, account_id=account.id, external_project_id="proj-1", name="Project 1"
        )
        assert project.name == "Project 1"


class TestCloudAccountService:
    async def test_register_account_publishes_event_and_audits(
        self, repos, organization_id: UUID, publisher
    ) -> None:
        provider = await _provider(repos, organization_id)
        audit = AuditService(repos.audit)
        service = CloudAccountService(repos.accounts, publish=publisher, audit=audit)
        account = await service.register_account(
            organization_id,
            provider_id=provider.id,
            external_account_id="123456789",
            name="prod-account",
            credential_ref="ref",
            credential_expires_at=None,
            actor_id="tester",
            now=NOW,
        )
        assert account.is_valid
        assert publisher.names() == ["CloudAccountRegistered"]

    async def test_register_account_refuses_empty_credential(
        self, repos, organization_id: UUID
    ) -> None:
        provider = await _provider(repos, organization_id)
        service = CloudAccountService(repos.accounts)
        with pytest.raises(CredentialRefusedError):
            await service.register_account(
                organization_id,
                provider_id=provider.id,
                external_account_id="123456789",
                name="prod-account",
                credential_ref="   ",
                credential_expires_at=None,
                actor_id=None,
                now=NOW,
            )

    async def test_revalidate_marks_healthy(self, repos, organization_id: UUID) -> None:
        provider = await _provider(repos, organization_id)
        account = await _account(repos, organization_id, provider.id)
        service = CloudAccountService(repos.accounts)
        revalidated = await service.revalidate(account, now=NOW)
        assert revalidated.is_valid
        assert revalidated.health_status.value == "healthy"

    async def test_revalidate_marks_unhealthy_on_expired_credential(
        self, repos, organization_id: UUID
    ) -> None:
        provider = await _provider(repos, organization_id)
        account = await _account(
            repos, organization_id, provider.id, credential_expires_at=NOW - timedelta(hours=1)
        )
        service = CloudAccountService(repos.accounts)
        revalidated = await service.revalidate(account, now=NOW)
        assert not revalidated.is_valid
        assert revalidated.health_status.value == "unhealthy"


class TestCloudResourceService:
    async def test_discover_publishes_event(self, repos, organization_id: UUID, publisher) -> None:
        provider = await _provider(repos, organization_id)
        account = await _account(repos, organization_id, provider.id)
        service = CloudResourceService(repos.resources, publish=publisher)
        resource = await service.discover(
            organization_id,
            account_id=account.id,
            resource_type=CloudResourceType.VIRTUAL_MACHINE,
            external_id="i-123",
            name="web-1",
            now=NOW,
        )
        assert resource.lifecycle_state == CloudResourceLifecycleState.DISCOVERED
        assert publisher.names() == ["CloudResourceDiscovered"]

    async def test_transition_lifecycle_provisioned_event(
        self, repos, organization_id: UUID, publisher
    ) -> None:
        provider = await _provider(repos, organization_id)
        account = await _account(repos, organization_id, provider.id)
        resource = await _resource(repos, organization_id, account.id)
        service = CloudResourceService(repos.resources, publish=publisher)
        await service.transition_lifecycle(
            resource, target=CloudResourceLifecycleState.PROVISIONING, actor_id=None, now=NOW
        )
        await service.transition_lifecycle(
            resource, target=CloudResourceLifecycleState.ACTIVE, actor_id=None, now=NOW
        )
        assert "CloudResourceProvisioned" in publisher.names()
        assert resource.provisioned_at == NOW

    async def test_transition_lifecycle_deleted_event(
        self, repos, organization_id: UUID, publisher
    ) -> None:
        provider = await _provider(repos, organization_id)
        account = await _account(repos, organization_id, provider.id)
        resource = await _resource(
            repos, organization_id, account.id, lifecycle_state=CloudResourceLifecycleState.ACTIVE
        )
        service = CloudResourceService(repos.resources, publish=publisher)
        await service.transition_lifecycle(
            resource, target=CloudResourceLifecycleState.DELETING, actor_id=None, now=NOW
        )
        await service.transition_lifecycle(
            resource, target=CloudResourceLifecycleState.DELETED, actor_id=None, now=NOW
        )
        assert "CloudResourceDeleted" in publisher.names()

    async def test_transition_lifecycle_refused(self, repos, organization_id: UUID) -> None:
        provider = await _provider(repos, organization_id)
        account = await _account(repos, organization_id, provider.id)
        resource = await _resource(repos, organization_id, account.id)
        service = CloudResourceService(repos.resources)
        with pytest.raises(TransitionRefusedError) as exc_info:
            await service.transition_lifecycle(
                resource, target=CloudResourceLifecycleState.ACTIVE, actor_id=None, now=NOW
            )
        assert exc_info.value.result.refusal == TransitionRefusal.INVALID_TRANSITION

    async def test_mark_synced(self, repos, organization_id: UUID) -> None:
        provider = await _provider(repos, organization_id)
        account = await _account(repos, organization_id, provider.id)
        resource = await _resource(repos, organization_id, account.id)
        service = CloudResourceService(repos.resources)
        synced = await service.mark_synced(resource, now=NOW)
        assert synced.last_synced_at == NOW


class TestResourceDetailServices:
    async def test_compute_attach_and_record_utilization(
        self, repos, organization_id: UUID
    ) -> None:
        provider = await _provider(repos, organization_id)
        account = await _account(repos, organization_id, provider.id)
        resource = await _resource(repos, organization_id, account.id)
        service = ComputeService(repos.compute)
        compute = await service.attach(
            organization_id, resource_id=resource.id, instance_type="t3.micro"
        )
        updated = await service.record_utilization(compute, utilization_fraction=0.5)
        assert updated.utilization_fraction == 0.5

    async def test_record_utilization_out_of_range_raises(
        self, repos, organization_id: UUID
    ) -> None:
        provider = await _provider(repos, organization_id)
        account = await _account(repos, organization_id, provider.id)
        resource = await _resource(repos, organization_id, account.id)
        service = ComputeService(repos.compute)
        compute = await service.attach(organization_id, resource_id=resource.id)
        with pytest.raises(ValueError, match="utilization_fraction"):
            await service.record_utilization(compute, utilization_fraction=1.5)

    async def test_storage_attach(self, repos, organization_id: UUID) -> None:
        provider = await _provider(repos, organization_id)
        account = await _account(repos, organization_id, provider.id)
        resource = await _resource(repos, organization_id, account.id)
        service = StorageService(repos.storage)
        storage = await service.attach(
            organization_id, resource_id=resource.id, storage_class="standard"
        )
        assert storage.storage_class == "standard"

    async def test_network_attach(self, repos, organization_id: UUID) -> None:
        provider = await _provider(repos, organization_id)
        account = await _account(repos, organization_id, provider.id)
        resource = await _resource(repos, organization_id, account.id)
        service = NetworkService(repos.networks)
        network = await service.attach(
            organization_id, resource_id=resource.id, cidr_block="10.0.0.0/16"
        )
        assert network.cidr_block == "10.0.0.0/16"

    async def test_database_attach(self, repos, organization_id: UUID) -> None:
        provider = await _provider(repos, organization_id)
        account = await _account(repos, organization_id, provider.id)
        resource = await _resource(repos, organization_id, account.id)
        service = DatabaseService(repos.databases)
        database = await service.attach(
            organization_id, resource_id=resource.id, engine="postgresql"
        )
        assert database.engine == "postgresql"

    async def test_kubernetes_attach(self, repos, organization_id: UUID) -> None:
        provider = await _provider(repos, organization_id)
        account = await _account(repos, organization_id, provider.id)
        resource = await _resource(repos, organization_id, account.id)
        service = KubernetesService(repos.kubernetes)
        cluster_ref = uuid4()
        kubernetes = await service.attach(
            organization_id,
            resource_id=resource.id,
            cluster_reference_id=cluster_ref,
            node_pool_count=3,
        )
        assert kubernetes.cluster_reference_id == cluster_ref
        assert kubernetes.node_pool_count == 3


class TestCloudPolicyService:
    async def test_create_activate_disable(self, repos, organization_id: UUID) -> None:
        audit = AuditService(repos.audit)
        service = CloudPolicyService(repos.policies, audit=audit)
        policy = await service.create_policy(
            organization_id,
            name="require-env-tag",
            policy_type=CloudPolicyType.TAG,
            definition={"required_keys": ["env"]},
            scope_account_id=None,
            actor_id="tester",
            now=NOW,
        )
        activated = await service.activate(policy)
        assert activated.status.value == "active"
        disabled = await service.disable(activated)
        assert disabled.status.value == "disabled"

    async def test_evaluate_tag_policy(self, repos, organization_id: UUID) -> None:
        service = CloudPolicyService(repos.policies)
        policy = await service.create_policy(
            organization_id,
            name="require-env-tag",
            policy_type=CloudPolicyType.TAG,
            definition={"required_keys": ["env"]},
            scope_account_id=None,
            actor_id=None,
            now=NOW,
        )
        result = service.evaluate(policy, tags={"env": "prod"})
        assert result.is_compliant
        missing = service.evaluate(policy, tags={})
        assert not missing.is_compliant

    async def test_evaluate_naming_policy(self, repos, organization_id: UUID) -> None:
        service = CloudPolicyService(repos.policies)
        policy = await service.create_policy(
            organization_id,
            name="prod-prefix",
            policy_type=CloudPolicyType.NAMING,
            definition={"pattern": "prod-.*"},
            scope_account_id=None,
            actor_id=None,
            now=NOW,
        )
        assert service.evaluate(policy, name="prod-vm-1").is_compliant
        assert not service.evaluate(policy, name="dev-vm-1").is_compliant

    async def test_evaluate_quota_policy(self, repos, organization_id: UUID) -> None:
        service = CloudPolicyService(repos.policies)
        policy = await service.create_policy(
            organization_id,
            name="max-vms",
            policy_type=CloudPolicyType.QUOTA,
            definition={"max_count": 5},
            scope_account_id=None,
            actor_id=None,
            now=NOW,
        )
        assert service.evaluate(policy, current_count=3).is_compliant
        assert not service.evaluate(policy, current_count=6).is_compliant

    async def test_evaluate_missing_attribute_raises(self, repos, organization_id: UUID) -> None:
        service = CloudPolicyService(repos.policies)
        policy = await service.create_policy(
            organization_id,
            name="require-env-tag",
            policy_type=CloudPolicyType.TAG,
            definition={},
            scope_account_id=None,
            actor_id=None,
            now=NOW,
        )
        with pytest.raises(ValueError, match="tags"):
            service.evaluate(policy)

    async def test_evaluate_naming_missing_name_raises(self, repos, organization_id: UUID) -> None:
        service = CloudPolicyService(repos.policies)
        policy = await service.create_policy(
            organization_id,
            name="prod-prefix",
            policy_type=CloudPolicyType.NAMING,
            definition={"pattern": "prod-.*"},
            scope_account_id=None,
            actor_id=None,
            now=NOW,
        )
        with pytest.raises(ValueError, match="name"):
            service.evaluate(policy)

    async def test_evaluate_quota_missing_current_count_raises(
        self, repos, organization_id: UUID
    ) -> None:
        service = CloudPolicyService(repos.policies)
        policy = await service.create_policy(
            organization_id,
            name="max-vms",
            policy_type=CloudPolicyType.QUOTA,
            definition={"max_count": 5},
            scope_account_id=None,
            actor_id=None,
            now=NOW,
        )
        with pytest.raises(ValueError, match="current_count"):
            service.evaluate(policy)

    async def test_evaluate_unhandled_policy_type_is_compliant(
        self, repos, organization_id: UUID
    ) -> None:
        service = CloudPolicyService(repos.policies)
        policy = await service.create_policy(
            organization_id,
            name="approval-required",
            policy_type=CloudPolicyType.APPROVAL,
            definition={},
            scope_account_id=None,
            actor_id=None,
            now=NOW,
        )
        result = service.evaluate(policy)
        assert result.is_compliant


class TestCloudCostAndBudgetServices:
    async def test_record_cost(self, repos, organization_id: UUID) -> None:
        provider = await _provider(repos, organization_id)
        account = await _account(repos, organization_id, provider.id)
        audit = AuditService(repos.audit)
        service = CloudCostService(repos.costs, audit=audit)
        cost = await service.record_cost(
            organization_id,
            account_id=account.id,
            resource_id=None,
            amount=42.50,
            currency="USD",
            cost_category="compute",
            period_start=NOW,
            period_end=NOW + timedelta(days=1),
            actor_id="tester",
            now=NOW,
        )
        assert cost.amount == 42.50

    async def test_create_budget_and_refresh_spend_publishes_on_crossing(
        self, repos, organization_id: UUID, publisher
    ) -> None:
        service = CloudBudgetService(repos.budgets, publish=publisher)
        budget = await service.create_budget(
            organization_id,
            account_id=None,
            name="Monthly",
            amount=100.0,
            period=BudgetPeriod.MONTHLY,
            threshold_fraction=0.8,
            period_start=NOW,
            period_end=NOW + timedelta(days=30),
        )
        status = await service.refresh_spend(budget, current_spend=90.0, critical_threshold=0.95)
        assert status == "warning"
        assert publisher.names() == ["BudgetThresholdExceeded"]

    async def test_refresh_spend_does_not_renotify_same_status(
        self, repos, organization_id: UUID, publisher
    ) -> None:
        service = CloudBudgetService(repos.budgets, publish=publisher)
        budget = await service.create_budget(
            organization_id,
            account_id=None,
            name="Monthly",
            amount=100.0,
            period=BudgetPeriod.MONTHLY,
            threshold_fraction=0.8,
            period_start=NOW,
            period_end=NOW + timedelta(days=30),
        )
        await service.refresh_spend(budget, current_spend=85.0, critical_threshold=0.95)
        await service.refresh_spend(budget, current_spend=86.0, critical_threshold=0.95)
        assert publisher.names() == ["BudgetThresholdExceeded"]


class TestCloudDriftService:
    async def test_check_records_and_publishes_on_drift(
        self, repos, organization_id: UUID, publisher
    ) -> None:
        provider = await _provider(repos, organization_id)
        account = await _account(repos, organization_id, provider.id)
        resource = await _resource(repos, organization_id, account.id)
        service = CloudDriftService(repos.drift, publish=publisher)
        drift = await service.check(
            organization_id,
            resource_id=resource.id,
            desired_state_hash="a",
            live_state_hash="b",
            drifted_field_count=4,
            high_threshold=3,
            critical_threshold=5,
            now=NOW,
        )
        assert drift is not None
        assert drift.severity.value == "high"
        assert publisher.names() == ["DriftDetected"]

    async def test_check_returns_none_when_not_drifted(self, repos, organization_id: UUID) -> None:
        provider = await _provider(repos, organization_id)
        account = await _account(repos, organization_id, provider.id)
        resource = await _resource(repos, organization_id, account.id)
        service = CloudDriftService(repos.drift)
        result = await service.check(
            organization_id,
            resource_id=resource.id,
            desired_state_hash="a",
            live_state_hash="a",
            drifted_field_count=0,
            high_threshold=3,
            critical_threshold=5,
            now=NOW,
        )
        assert result is None

    async def test_resolve_and_acknowledge(self, repos, organization_id: UUID) -> None:
        provider = await _provider(repos, organization_id)
        account = await _account(repos, organization_id, provider.id)
        resource = await _resource(repos, organization_id, account.id)
        service = CloudDriftService(repos.drift)
        drift = await service.check(
            organization_id,
            resource_id=resource.id,
            desired_state_hash="a",
            live_state_hash="b",
            drifted_field_count=1,
            high_threshold=3,
            critical_threshold=5,
            now=NOW,
        )
        assert drift is not None
        acknowledged = await service.acknowledge(drift)
        assert acknowledged.status == DriftStatus.ACKNOWLEDGED
        resolved = await service.resolve(acknowledged, now=NOW)
        assert resolved.status == DriftStatus.RESOLVED


class TestCloudIaCService:
    async def test_plan_and_transition_to_applied(self, repos, organization_id: UUID) -> None:
        audit = AuditService(repos.audit)
        service = CloudIaCService(repos.iac, audit=audit)
        deployment = await service.plan(
            organization_id,
            resource_id=None,
            tool=IaCTool.TERRAFORM,
            state_reference="s3://state",
            version_label="1.0.0",
        )
        applying = await service.transition(
            deployment, target=IaCDeploymentStatus.APPLYING, actor_id="tester", now=NOW
        )
        applied = await service.transition(
            applying, target=IaCDeploymentStatus.APPLIED, actor_id="tester", now=NOW
        )
        assert applied.applied_at == NOW

    async def test_transition_refused(self, repos, organization_id: UUID) -> None:
        service = CloudIaCService(repos.iac)
        deployment = await service.plan(
            organization_id,
            resource_id=None,
            tool=IaCTool.TERRAFORM,
            state_reference=None,
            version_label=None,
        )
        with pytest.raises(IaCTransitionRefusedError) as exc_info:
            await service.transition(
                deployment, target=IaCDeploymentStatus.APPLIED, actor_id=None, now=NOW
            )
        assert exc_info.value.result.refusal == IaCTransitionRefusal.INVALID_TRANSITION


class TestCloudCatalogService:
    async def test_create_and_approval_workflow(self, repos, organization_id: UUID) -> None:
        service = CloudCatalogService(repos.catalog)
        item = await service.create_item(
            organization_id,
            name="Standard VM",
            description=None,
            resource_type=CloudResourceType.VIRTUAL_MACHINE,
            version_label="1.0.0",
            template={},
        )
        pending = await service.transition(item, target=CatalogItemStatus.PENDING_APPROVAL)
        approved = await service.transition(pending, target=CatalogItemStatus.APPROVED)
        assert approved.status == CatalogItemStatus.APPROVED

    async def test_transition_refused(self, repos, organization_id: UUID) -> None:
        service = CloudCatalogService(repos.catalog)
        item = await service.create_item(
            organization_id,
            name="Standard VM",
            description=None,
            resource_type=CloudResourceType.VIRTUAL_MACHINE,
            version_label="1.0.0",
            template={},
        )
        with pytest.raises(CatalogTransitionRefusedError) as exc_info:
            await service.transition(item, target=CatalogItemStatus.APPROVED)
        assert exc_info.value.result.refusal == CatalogTransitionRefusal.INVALID_TRANSITION


class TestCloudComplianceService:
    async def test_assess_sets_remediation_due_for_non_compliant(
        self, repos, organization_id: UUID
    ) -> None:
        provider = await _provider(repos, organization_id)
        account = await _account(repos, organization_id, provider.id)
        audit = AuditService(repos.audit)
        service = CloudComplianceService(repos.compliance, audit=audit)
        assessment = await service.assess(
            organization_id,
            account_id=account.id,
            framework=CloudComplianceFramework.CIS,
            score=30.0,
            compliant_threshold=90,
            partial_threshold=60,
            remediation_grace_days=14,
            actor_id="tester",
            now=NOW,
        )
        assert assessment.status.value == "non_compliant"
        assert assessment.remediation_due_at == NOW + timedelta(days=14)

    async def test_assess_compliant_has_no_remediation(self, repos, organization_id: UUID) -> None:
        provider = await _provider(repos, organization_id)
        account = await _account(repos, organization_id, provider.id)
        service = CloudComplianceService(repos.compliance)
        assessment = await service.assess(
            organization_id,
            account_id=account.id,
            framework=CloudComplianceFramework.CIS,
            score=95.0,
            compliant_threshold=90,
            partial_threshold=60,
            remediation_grace_days=14,
            actor_id=None,
            now=NOW,
        )
        assert assessment.status.value == "compliant"
        assert assessment.remediation_due_at is None


class TestStatisticsService:
    async def test_roll_up_window_is_idempotent(self, repos, organization_id: UUID) -> None:
        service = StatisticsService(repos.statistics)
        window_start = NOW
        window_end = NOW + timedelta(hours=1)
        first = await service.roll_up_window(
            organization_id,
            window_start=window_start,
            window_end=window_end,
            resources_discovered=1,
            resources_provisioned=1,
            total_cost=10.0,
            budgets_exceeded=0,
            drift_detected_count=0,
            compliance_violations=0,
        )
        second = await service.roll_up_window(
            organization_id,
            window_start=window_start,
            window_end=window_end,
            resources_discovered=5,
            resources_provisioned=2,
            total_cost=20.0,
            budgets_exceeded=1,
            drift_detected_count=1,
            compliance_violations=1,
        )
        assert first.id == second.id
        assert second.resources_discovered == 5


class TestReportService:
    async def test_generate(self, repos, organization_id: UUID) -> None:
        from app.models.enums import ReportFormat, ReportKind

        service = ReportService(repos.reports)
        report = await service.generate(
            organization_id,
            kind=ReportKind.COST,
            title="Cost Report",
            report_format=ReportFormat.JSON,
            period_start=None,
            period_end=None,
            content={"total": 100},
            row_count=1,
            generated_by="tester",
            now=NOW,
        )
        assert report.status.value == "completed"
