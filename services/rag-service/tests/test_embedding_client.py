"""The embedding provider client, over a mock HTTP transport.

``httpx.MockTransport`` is the transport, not a mock of the client: the
real request is built, the real response is parsed, and only the socket is
replaced. That is what makes these tests able to catch a malformed payload
or a misread response body -- the two things that actually go wrong with a
provider client, and the two things mocking the client itself would hide.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from shared_core.exceptions.dependency import DependencyError

from app.embeddings.client import EmbeddingClient, EmbeddingRequest, build_client
from app.models.enums import EmbeddingProvider

pytestmark = pytest.mark.asyncio

DIMENSIONS = 4


def _vector(seed: float) -> list[float]:
    return [seed] * DIMENSIONS


def _openai_body(count: int, *, shuffled: bool = False) -> dict[str, Any]:
    indices = list(range(count))
    if shuffled:
        indices.reverse()
    return {
        "data": [{"index": index, "embedding": _vector(float(index) + 1.0)} for index in indices],
        "usage": {"total_tokens": 10},
    }


def _client(
    handler: Any,
    *,
    provider: EmbeddingProvider = EmbeddingProvider.OPENAI,
    ollama_style: bool = False,
) -> tuple[EmbeddingClient, httpx.AsyncClient]:
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return (
        EmbeddingClient(
            http,
            provider=provider,
            base_url="https://api.example.com",
            api_key="k",
            ollama_style=ollama_style,
        ),
        http,
    )


async def test_a_request_carries_its_texts_and_model() -> None:
    request = EmbeddingRequest(texts=["a", "b"], model="m")
    assert request.texts == ["a", "b"]
    assert request.model == "m"


async def test_openai_vectors_come_back_in_input_order() -> None:
    """The provider is free to return the array in any order; it carries
    an ``index`` for exactly that reason, and ignoring it pairs every
    chunk with another chunk's vector."""
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["payload"] = json.loads(request.content)
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json=_openai_body(3, shuffled=True))

    client, http = _client(handler)
    async with http:
        vectors = await client.embed(["a", "b", "c"], model="text-embedding-3-small")

    assert vectors == [_vector(1.0), _vector(2.0), _vector(3.0)]
    assert seen["url"].endswith("/embeddings")
    assert seen["payload"]["input"] == ["a", "b", "c"]
    assert seen["auth"] == "Bearer k"


async def test_ollama_uses_its_own_endpoint_path() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"embeddings": [_vector(1.0), _vector(2.0)]})

    client, http = _client(handler, provider=EmbeddingProvider.OLLAMA, ollama_style=True)
    async with http:
        vectors = await client.embed(["a", "b"], model="nomic")

    assert len(vectors) == 2
    assert seen["url"].endswith("/api/embed")


async def test_a_provider_error_status_is_refused() -> None:
    """A 429 that returned an empty list would look like a corpus with no
    matches rather than a quota that ran out."""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "rate limited"})

    client, http = _client(handler)
    async with http:
        with pytest.raises(DependencyError):
            await client.embed(["a"], model="m")


async def test_a_transport_failure_is_refused() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route to host")

    client, http = _client(handler)
    async with http:
        with pytest.raises(DependencyError):
            await client.embed(["a"], model="m")


async def test_a_non_json_response_is_refused() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>gateway</html>")

    client, http = _client(handler)
    async with http:
        with pytest.raises(DependencyError):
            await client.embed(["a"], model="m")


async def test_a_short_batch_is_refused_rather_than_padded() -> None:
    """Two vectors for three chunks means the third chunk would get
    somebody else's vector, or none -- and both are silent."""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_openai_body(2))

    client, http = _client(handler)
    async with http:
        with pytest.raises(DependencyError):
            await client.embed(["a", "b", "c"], model="m")


async def test_a_response_with_no_vectors_is_refused() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": []})

    client, http = _client(handler)
    async with http:
        with pytest.raises(DependencyError):
            await client.embed(["a"], model="m")


async def test_a_malformed_vector_is_refused() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": "not a vector"}]})

    client, http = _client(handler)
    async with http:
        with pytest.raises(DependencyError):
            await client.embed(["a"], model="m")


async def test_embedding_nothing_is_refused_rather_than_sent() -> None:
    """An empty batch is a caller bug, and a provider round trip that
    returns nothing looks identical to one that failed."""
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json=_openai_body(0))

    client, http = _client(handler)
    async with http:
        with pytest.raises((ValueError, DependencyError)):
            await client.embed([], model="m")
    assert calls == []


async def test_the_client_reports_its_provider() -> None:
    client, http = _client(lambda _r: httpx.Response(200, json=_openai_body(1)))
    async with http:
        assert client.provider is EmbeddingProvider.OPENAI


async def test_azure_openai_is_built_when_given_a_base_url() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _r: httpx.Response(200, json=_openai_body(1)))
    ) as http:
        built = build_client(
            http,
            provider=EmbeddingProvider.AZURE_OPENAI,
            base_url="https://example.openai.azure.com",
            api_key="k",
        )
        assert built is not None
        assert built.provider is EmbeddingProvider.AZURE_OPENAI


async def test_a_provider_with_no_base_url_is_refused_at_configuration_time() -> None:
    """Refused when the client is built rather than at the first
    production ingestion."""
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _r: httpx.Response(200, json=_openai_body(1)))
    ) as http:
        with pytest.raises(DependencyError, match="base URL"):
            build_client(http, provider=EmbeddingProvider.OPENAI, base_url="")
