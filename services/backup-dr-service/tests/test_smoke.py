"""Smoke test: conftest fixtures build against real infrastructure."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import HTTP_OK


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == HTTP_OK
