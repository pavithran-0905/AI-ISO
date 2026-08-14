"""Tests for app.policies.engine: target resolution and drift detection."""

from __future__ import annotations

from uuid import uuid4

from app.policies.engine import TargetRefusal, detect_drift, resolve_targets


class TestResolveTargets:
    def test_cluster_scoped_targets_one_cluster(self) -> None:
        cid = uuid4()
        result = resolve_targets(cluster_id=cid, group_id=None)
        assert result.is_resolved
        assert result.target_cluster_ids == (cid,)

    def test_group_scoped_targets_every_member(self) -> None:
        gid = uuid4()
        members = [uuid4(), uuid4(), uuid4()]
        result = resolve_targets(cluster_id=None, group_id=gid, cluster_ids_in_group=members)
        assert result.is_resolved
        assert result.target_cluster_ids == tuple(members)

    def test_no_target_refused(self) -> None:
        result = resolve_targets(cluster_id=None, group_id=None)
        assert not result.is_resolved
        assert result.refusal == TargetRefusal.NO_TARGET

    def test_cluster_id_takes_precedence_over_group(self) -> None:
        cid = uuid4()
        gid = uuid4()
        result = resolve_targets(cluster_id=cid, group_id=gid, cluster_ids_in_group=[uuid4()])
        assert result.target_cluster_ids == (cid,)

    def test_empty_group_targets_nothing_but_is_resolved(self) -> None:
        gid = uuid4()
        result = resolve_targets(cluster_id=None, group_id=gid, cluster_ids_in_group=[])
        assert result.is_resolved
        assert result.target_cluster_ids == ()


class TestDetectDrift:
    def test_never_observed_is_not_drift(self) -> None:
        assert not detect_drift("desired-hash", None)

    def test_matching_hash_is_not_drift(self) -> None:
        assert not detect_drift("abc", "abc")

    def test_mismatched_hash_is_drift(self) -> None:
        assert detect_drift("abc", "xyz")
