"""Embedding provider clients (docs/062 "EMBEDDING MODELS").

One HTTP client covering the providers that speak an OpenAI-compatible
``POST /embeddings``, plus Ollama's own ``POST /api/embed``. Ported from
``ai-assistant-service/app/clients/embedding_client.py``.

**The response ordering trap.** OpenAI's response carries an ``index``
per embedding and does not guarantee array order matches request order.
Zipping the raw array against the input list would silently pair vector 3
with chunk 1 -- producing a fully populated index where every embedding
belongs to the wrong text, which no downstream check would catch because
every vector is individually valid. The response is sorted by ``index``
before use, and a count mismatch is refused outright.

**Which providers are real here.** OpenAI, Azure OpenAI, and any
OpenAI-compatible endpoint (vLLM, LocalAI, OpenRouter) share one wire
format and are all exercised by the same code path. Ollama has its own.
Voyage and Cohere are *declared* in the enum and rejected here with a
clear error rather than guessed at -- their wire formats differ and
writing a client against documentation without ever running it is how
you ship something that has never worked.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx
from shared_core.exceptions.dependency import DependencyError
from shared_core.logging.logger import get_logger

from app.models.enums import EmbeddingProvider

logger = get_logger("app.embeddings.client")

_OPENAI_COMPATIBLE = frozenset(
    {
        EmbeddingProvider.OPENAI,
        EmbeddingProvider.AZURE_OPENAI,
        EmbeddingProvider.SENTENCE_TRANSFORMERS,
        EmbeddingProvider.BGE,
        EmbeddingProvider.E5,
        EmbeddingProvider.CUSTOM,
    }
)
"""All served behind an OpenAI-compatible endpoint in practice. BGE and
E5 are model families, not hosted APIs -- they are reached through vLLM,
text-embeddings-inference, or similar, every one of which implements
``POST /embeddings``."""

_UNSUPPORTED = frozenset(
    {EmbeddingProvider.VOYAGE, EmbeddingProvider.COHERE, EmbeddingProvider.GEMINI}
)
"""Declared in the enum, no client here. Each has a distinct wire format,
and a client written from documentation and never run against the real
service is worse than an honest refusal -- it fails at the first
production ingestion instead of at configuration time."""


@dataclass(frozen=True, slots=True)
class EmbeddingRequest:
    """One batch of texts to embed."""

    texts: list[str]
    model: str

    def __post_init__(self) -> None:
        if not self.texts:
            raise ValueError("Cannot embed an empty batch.")
        if any(not text.strip() for text in self.texts):
            raise ValueError(
                "Cannot embed blank text. A blank string produces a vector that "
                "matches queries for no reason; drop the chunk instead."
            )


class EmbeddingClient:
    """Calls one embedding provider over HTTP."""

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        *,
        provider: EmbeddingProvider,
        base_url: str,
        api_key: str = "",
        ollama_style: bool = False,
    ) -> None:
        self._http = http_client
        self._provider = provider
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._ollama_style = ollama_style

    @property
    def provider(self) -> EmbeddingProvider:
        return self._provider

    async def embed(self, texts: list[str], *, model: str) -> list[list[float]]:
        """Embed *texts*, returning vectors in the same order.

        Raises:
            DependencyError: If the provider is unreachable, returns a
                non-JSON body, returns an unexpected shape, or returns a
                different number of embeddings than were requested.
        """
        request = EmbeddingRequest(texts=list(texts), model=model)
        payload, url = self._build(request)

        try:
            response = await self._http.post(url, json=payload, headers=self._headers())
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise DependencyError(
                f"Embedding provider {self._provider!s} returned "
                f"{exc.response.status_code} for {len(texts)} text(s)."
            ) from exc
        except httpx.HTTPError as exc:
            raise DependencyError(
                f"Embedding provider {self._provider!s} is unreachable: {exc}"
            ) from exc

        vectors = self._parse(response, expected=len(request.texts))
        logger.info(
            "Embedded a batch.",
            extra={
                "extra_fields": {
                    "provider": str(self._provider),
                    "model": model,
                    "count": len(vectors),
                    "dimensions": len(vectors[0]) if vectors else 0,
                }
            },
        )
        return vectors

    def _build(self, request: EmbeddingRequest) -> tuple[dict[str, object], str]:
        if self._ollama_style:
            return ({"model": request.model, "input": request.texts}, f"{self._base_url}/api/embed")
        return ({"model": request.model, "input": request.texts}, f"{self._base_url}/embeddings")

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _parse(self, response: httpx.Response, *, expected: int) -> list[list[float]]:
        """Extract vectors, in request order, or fail loudly."""
        try:
            body = response.json()
        except ValueError as exc:
            raise DependencyError(
                f"Embedding provider {self._provider!s} returned a non-JSON body: {exc}"
            ) from exc
        if not isinstance(body, dict):
            raise DependencyError(
                f"Embedding provider {self._provider!s} returned {type(body).__name__}, "
                "not a JSON object."
            )

        vectors = self._ollama_vectors(body) if self._ollama_style else self._openai_vectors(body)

        if len(vectors) != expected:
            raise DependencyError(
                f"Embedding provider {self._provider!s} returned {len(vectors)} "
                f"embeddings for {expected} input(s). Pairing them by position "
                "would attach vectors to the wrong text, so the batch is refused."
            )
        return vectors

    def _openai_vectors(self, body: dict[str, object]) -> list[list[float]]:
        data = body.get("data")
        if not isinstance(data, list):
            raise DependencyError(
                f"Embedding provider {self._provider!s} returned no 'data' array."
            )
        entries: list[tuple[int, list[float]]] = []
        for position, entry in enumerate(data):
            if not isinstance(entry, dict):
                raise DependencyError(
                    f"Embedding provider {self._provider!s} returned a non-object "
                    "entry in 'data'."
                )
            vector = entry.get("embedding")
            if not isinstance(vector, list):
                raise DependencyError(
                    f"Embedding provider {self._provider!s} returned an entry with "
                    "no 'embedding' array."
                )
            index = entry.get("index")
            entries.append((index if isinstance(index, int) else position, _floats(vector)))
        # Sorted by the provider's own index, never left in array order.
        # See this module's docstring for why that matters.
        entries.sort(key=lambda pair: pair[0])
        return [vector for _index, vector in entries]

    def _ollama_vectors(self, body: dict[str, object]) -> list[list[float]]:
        embeddings = body.get("embeddings")
        if not isinstance(embeddings, list):
            raise DependencyError(
                f"Embedding provider {self._provider!s} returned no 'embeddings' array."
            )
        return [_floats(vector) for vector in embeddings if isinstance(vector, list)]


def _floats(values: list[object]) -> list[float]:
    """Coerce a JSON array to floats.

    Raises:
        DependencyError: If any element is not numeric. A vector with a
            string in it would be stored, and every distance computed
            against it afterwards would be wrong.
    """
    try:
        return [float(value) for value in values]  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise DependencyError(f"An embedding contained a non-numeric value: {exc}") from exc


def build_client(
    http_client: httpx.AsyncClient,
    *,
    provider: EmbeddingProvider,
    base_url: str,
    api_key: str = "",
) -> EmbeddingClient | None:
    """Build the client for *provider*, or ``None`` for ``BUILTIN``.

    ``None`` is the signal to use :class:`~app.embeddings.encoder
    .HashingEncoder` -- the builtin encoder is not an HTTP client and
    pretending it is would mean giving it a fake base URL.

    Raises:
        DependencyError: For a provider with no client here, or for one
            that needs a base URL and was given none.
    """
    chosen = EmbeddingProvider(provider)
    if chosen is EmbeddingProvider.BUILTIN:
        return None
    if chosen in _UNSUPPORTED:
        raise DependencyError(
            f"Embedding provider {chosen!s} has no client in this service. Its wire "
            "format differs from the OpenAI-compatible one, and shipping a client "
            "written from documentation but never run against the real API would "
            "fail at the first production ingestion rather than here at "
            "configuration time."
        )
    if not base_url:
        raise DependencyError(
            f"Embedding provider {chosen!s} needs a base URL "
            "(AIIOS_RAG_SERVICE_EMBEDDING_BASE_URL)."
        )
    return EmbeddingClient(
        http_client,
        provider=chosen,
        base_url=base_url,
        api_key=api_key,
        ollama_style=chosen is EmbeddingProvider.OLLAMA,
    )


__all__ = ["EmbeddingClient", "EmbeddingRequest", "build_client"]
