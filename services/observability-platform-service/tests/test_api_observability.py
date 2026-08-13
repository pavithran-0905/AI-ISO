"""Integration tests for the 13 REST routes, through the real FastAPI app
and real database (see tests/conftest.py's ``app``/``client`` fixtures)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from httpx import AsyncClient

from app.models.enums import MetricKind, MetricType, SourceKind
from app.models.signals import MetricSeries

NOW = datetime(2026, 6, 1, tzinfo=UTC)


class TestHealthRoutes:
    async def test_health(self, client: AsyncClient) -> None:
        response = await client.get("/health")
        assert response.status_code == 200

    async def test_metrics_endpoint(self, client: AsyncClient) -> None:
        response = await client.get("/metrics")
        assert response.status_code == 200


class TestAuthGating:
    async def test_all_get_routes_reject_unauthenticated(self, client: AsyncClient) -> None:
        paths = [
            f"/observability/metrics?series_id={uuid4()}",
            "/observability/logs",
            "/observability/traces?trace_id=t1",
            "/observability/events",
            "/observability/topology",
            "/observability/slos",
            "/observability/anomalies",
            "/observability/root-cause?service_name=x",
            "/observability/capacity",
            f"/observability/cost?period_start={NOW.isoformat()}&period_end={NOW.isoformat()}",
            "/observability/statistics",
            "/observability/reports",
        ]
        for path in paths:
            response = await client.get(path)
            assert response.status_code == 401, path

    async def test_post_slo_rejects_non_admin(self, client: AsyncClient, auth_headers) -> None:
        headers = auth_headers(organization_id=uuid4(), roles=["viewer"])
        response = await client.post(
            "/observability/slos",
            headers=headers,
            json={"name": "x", "service_name": "y", "sli_kind": "availability", "target": 0.9},
        )
        assert response.status_code == 403

    async def test_missing_organization_claim_rejected(
        self, client: AsyncClient, auth_headers
    ) -> None:
        headers = auth_headers(organization_id=None)
        response = await client.get("/observability/slos", headers=headers)
        assert response.status_code == 403


class TestSloRoutes:
    async def test_create_and_list_slo(
        self, client: AsyncClient, auth_headers, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id, roles=["observability_admin"])
        create_response = await client.post(
            "/observability/slos",
            headers=headers,
            json={
                "name": "api-availability",
                "service_name": "gateway",
                "sli_kind": "availability",
                "target": 0.999,
                "window_days": 30,
            },
        )
        assert create_response.status_code == 201
        list_response = await client.get("/observability/slos", headers=headers)
        assert list_response.status_code == 200
        body = list_response.json()
        assert body["data"]["total"] == 1

    async def test_create_slo_validation_error(
        self, client: AsyncClient, auth_headers, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id, roles=["observability_admin"])
        response = await client.post(
            "/observability/slos",
            headers=headers,
            json={"name": "x", "service_name": "y", "sli_kind": "availability", "target": 1.5},
        )
        assert response.status_code in (400, 422)


class TestMetricsRoute:
    async def test_get_metrics_404_for_unknown_series(
        self, client: AsyncClient, auth_headers, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get(f"/observability/metrics?series_id={uuid4()}", headers=headers)
        assert response.status_code == 404

    async def test_get_metrics_missing_series_id_returns_422(
        self, client: AsyncClient, auth_headers, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/observability/metrics", headers=headers)
        assert response.status_code in (400, 422)

    async def test_get_metrics_for_real_series(
        self, client: AsyncClient, auth_headers, organization_id: UUID, repos
    ) -> None:
        series = await repos.metric_series.create(
            MetricSeries(
                organization_id=organization_id,
                name="cpu",
                metric_type=MetricType.GAUGE,
                metric_kind=MetricKind.CUSTOM,
                labels={},
                label_fingerprint="fp-api",
                source_kind=SourceKind.CUSTOM_APPLICATION,
                first_seen_at=NOW,
                last_seen_at=NOW,
                sample_count=0,
            )
        )
        headers = auth_headers(organization_id=organization_id)
        response = await client.get(
            f"/observability/metrics?series_id={series.id}", headers=headers
        )
        assert response.status_code == 200
        assert response.json()["data"]["series"]["id"] == str(series.id)


class TestLogsAndEventsRoutes:
    async def test_get_logs_empty_ok(
        self, client: AsyncClient, auth_headers, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/observability/logs", headers=headers)
        assert response.status_code == 200
        assert response.json()["data"]["entries"] == []

    async def test_get_events_empty_ok(
        self, client: AsyncClient, auth_headers, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/observability/events", headers=headers)
        assert response.status_code == 200


class TestTraceRoute:
    async def test_unknown_trace_returns_404(
        self, client: AsyncClient, auth_headers, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/observability/traces?trace_id=missing", headers=headers)
        assert response.status_code == 404


class TestTopologyRoute:
    async def test_empty_topology(
        self, client: AsyncClient, auth_headers, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/observability/topology", headers=headers)
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["nodes"] == []
        assert data["edges"] == []


class TestAnomaliesRoute:
    async def test_empty_anomalies(
        self, client: AsyncClient, auth_headers, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/observability/anomalies", headers=headers)
        assert response.status_code == 200
        assert response.json()["data"]["total"] == 0


class TestRootCauseRoute:
    async def test_requires_service_name(
        self, client: AsyncClient, auth_headers, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/observability/root-cause", headers=headers)
        assert response.status_code in (400, 422)

    async def test_empty_root_causes(
        self, client: AsyncClient, auth_headers, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get(
            "/observability/root-cause?service_name=checkout", headers=headers
        )
        assert response.status_code == 200


class TestCapacityRoute:
    async def test_empty_capacity(
        self, client: AsyncClient, auth_headers, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/observability/capacity", headers=headers)
        assert response.status_code == 200


class TestCostRoute:
    async def test_requires_period_bounds(
        self, client: AsyncClient, auth_headers, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/observability/cost", headers=headers)
        assert response.status_code in (400, 422)

    async def test_empty_cost_reports(
        self, client: AsyncClient, auth_headers, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get(
            "/observability/cost",
            params={
                "period_start": (NOW - timedelta(days=1)).isoformat(),
                "period_end": NOW.isoformat(),
            },
            headers=headers,
        )
        assert response.status_code == 200


class TestStatisticsRoute:
    async def test_empty_statistics(
        self, client: AsyncClient, auth_headers, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/observability/statistics", headers=headers)
        assert response.status_code == 200


class TestReportsRoute:
    async def test_empty_reports(
        self, client: AsyncClient, auth_headers, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/observability/reports", headers=headers)
        assert response.status_code == 200

    async def test_reports_status_filter(
        self, client: AsyncClient, auth_headers, organization_id: UUID
    ) -> None:
        headers = auth_headers(organization_id=organization_id)
        response = await client.get("/observability/reports?status=completed", headers=headers)
        assert response.status_code == 200
