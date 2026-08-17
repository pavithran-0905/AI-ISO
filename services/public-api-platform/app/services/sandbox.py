"""Developer sandbox session management and mock service resolution.

Like usage, quotas, and documentation, there is no dedicated REST route
for either table -- a sandbox session is provisioned internally (or in
tests, directly) when a developer starts exploring a product, and
``SandboxResetSweepWorker`` is what actually resets a stale one, not a
route.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models.enums import MockType, SandboxStatus
from app.models.sandbox import ApiMockService, ApiSandboxSession
from app.repositories.sandbox import ApiMockServiceRepository, ApiSandboxSessionRepository
from app.sandbox.engine import MockOutcome, resolve_mock_response


class SandboxService:
    def __init__(self, repo: ApiSandboxSessionRepository) -> None:
        self._repo = repo

    async def start(
        self,
        organization_id: UUID,
        *,
        developer_account_id: UUID,
        api_product_id: UUID,
        now: datetime,
    ) -> ApiSandboxSession:
        return await self._repo.create(
            ApiSandboxSession(
                organization_id=organization_id,
                developer_account_id=developer_account_id,
                api_product_id=api_product_id,
                last_reset_at=now,
            )
        )

    async def reset(self, session: ApiSandboxSession, *, now: datetime) -> ApiSandboxSession:
        session.call_count = 0
        session.last_reset_at = now
        session.status = SandboxStatus.RESET
        return await self._repo.update(session)


class MockServiceConfig:
    def __init__(self, repo: ApiMockServiceRepository) -> None:
        self._repo = repo

    async def define(
        self,
        organization_id: UUID,
        *,
        api_product_id: UUID,
        endpoint_path: str,
        mock_type: MockType,
        response_body: dict[str, object],
        response_status_code: int = 200,
        simulated_latency_ms: float = 0.0,
        simulate_error: bool = False,
    ) -> ApiMockService:
        return await self._repo.create(
            ApiMockService(
                organization_id=organization_id,
                api_product_id=api_product_id,
                endpoint_path=endpoint_path,
                mock_type=mock_type,
                response_body=response_body,
                response_status_code=response_status_code,
                simulated_latency_ms=simulated_latency_ms,
                simulate_error=simulate_error,
            )
        )

    @staticmethod
    def resolve(mock: ApiMockService) -> MockOutcome:
        return resolve_mock_response(
            mock_type=MockType(mock.mock_type),
            response_body=mock.response_body,
            response_status_code=mock.response_status_code,
            simulated_latency_ms=mock.simulated_latency_ms,
            simulate_error=mock.simulate_error,
        )


__all__ = ["MockServiceConfig", "SandboxService"]
