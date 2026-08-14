"""Tests for app.federation.engine: cross-cluster distribution planning."""

from __future__ import annotations

from uuid import uuid4

from app.federation.engine import DistributionRefusal, plan_distribution


class TestPlanDistribution:
    def test_plans_to_distinct_targets(self) -> None:
        src = uuid4()
        t1 = uuid4()
        t2 = uuid4()
        plan = plan_distribution(src, [t1, t2])
        assert plan.is_planned
        assert plan.target_cluster_ids == (t1, t2)

    def test_excludes_source_from_its_own_targets(self) -> None:
        src = uuid4()
        t1 = uuid4()
        plan = plan_distribution(src, [t1, src])
        assert plan.target_cluster_ids == (t1,)

    def test_deduplicates_targets(self) -> None:
        src = uuid4()
        t1 = uuid4()
        plan = plan_distribution(src, [t1, t1, t1])
        assert plan.target_cluster_ids == (t1,)

    def test_preserves_first_appearance_order(self) -> None:
        src = uuid4()
        t1, t2, t3 = uuid4(), uuid4(), uuid4()
        plan = plan_distribution(src, [t3, t1, t2, t1])
        assert plan.target_cluster_ids == (t3, t1, t2)

    def test_only_source_in_targets_refused(self) -> None:
        src = uuid4()
        plan = plan_distribution(src, [src])
        assert not plan.is_planned
        assert plan.refusal == DistributionRefusal.NO_TARGETS

    def test_empty_targets_refused(self) -> None:
        src = uuid4()
        plan = plan_distribution(src, [])
        assert not plan.is_planned
        assert plan.refusal == DistributionRefusal.NO_TARGETS
