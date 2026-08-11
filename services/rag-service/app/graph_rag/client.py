"""Neo4j access for GraphRAG (docs/062 "GRAPHRAG", integrating Prompt 049).

Ported from ``knowledge-graph-service/app/graph/client.py`` -- services
cannot import each other, and ``shared_core`` carries only
:class:`~shared_core.config.settings.Neo4jSettings`, no driver wrapper.
Every consumer in this monorepo rolls its own for the same reason.

**GraphRAG is optional, and its absence must not break retrieval.** A
deployment with no knowledge graph is a normal deployment: vector and
keyword retrieval work perfectly without one. So the client is
constructible in a disabled state, every method returns empty rather
than raising when disabled, and a Neo4j outage degrades the graph arm to
zero results instead of failing the whole query. A hybrid search that
dies because one of three arms is unavailable is worse than one that
returns the other two.

**Only read queries.** This service consumes a graph that
knowledge-graph-service owns; writing to it from here would give two
services authority over one dataset with no coordination between them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from neo4j import AsyncDriver, AsyncGraphDatabase
from shared_core.config.settings import Neo4jSettings
from shared_core.logging.logger import get_logger

logger = get_logger("app.graph_rag.client")

DEFAULT_MAX_RECORDS = 1_000
"""A traversal that returns the whole graph is not retrieval. Bounded so
a runaway query cannot exhaust memory building a result nobody wants."""


@dataclass(frozen=True, slots=True)
class GraphNode:
    """One node returned from the graph."""

    key: str
    labels: tuple[str, ...] = ()
    properties: dict[str, Any] = field(default_factory=dict)

    @property
    def name(self) -> str:
        """A human-readable label, falling back to the key."""
        for candidate in ("name", "title", "display_name"):
            value = self.properties.get(candidate)
            if isinstance(value, str) and value.strip():
                return value
        return self.key

    def as_text(self) -> str:
        """Render this node as a sentence retrieval can use.

        A graph node is structure, not prose, and embedding ``{"key":
        "svc-01", "labels": ["Service"]}`` would embed JSON punctuation.
        Rendering it as ``"svc-01 (Service): owner=platform"`` gives the
        retriever something with the same shape as the document text it
        sits alongside.
        """
        labels = ", ".join(self.labels) if self.labels else "node"
        details = ", ".join(
            f"{key}={value}"
            for key, value in sorted(self.properties.items())
            if key not in {"key", "organization_id"} and value not in (None, "")
        )
        return f"{self.name} ({labels}){': ' + details if details else ''}"


@dataclass(frozen=True, slots=True)
class GraphRelationship:
    """One edge between two nodes."""

    type: str
    start_key: str
    end_key: str
    properties: dict[str, Any] = field(default_factory=dict)

    def as_text(self) -> str:
        return f"{self.start_key} -[{self.type}]-> {self.end_key}"


@dataclass(slots=True)
class Subgraph:
    """A connected fragment of the graph."""

    nodes: list[GraphNode] = field(default_factory=list)
    relationships: list[GraphRelationship] = field(default_factory=list)
    truncated: bool = False

    @property
    def is_empty(self) -> bool:
        return not self.nodes

    def as_text(self) -> str:
        """The whole subgraph as retrievable prose."""
        lines = [node.as_text() for node in self.nodes]
        lines.extend(edge.as_text() for edge in self.relationships)
        return "\n".join(lines)


def create_driver(
    settings: Neo4jSettings,
    *,
    enabled: bool = True,
    max_pool_size: int = 20,
    connection_timeout: float = 10.0,
) -> AsyncDriver | None:
    """Build a Neo4j driver, or ``None`` when GraphRAG is disabled.

    Construction is fully lazy in the Neo4j driver -- it does not connect
    until a query runs -- so a malformed host produces no error here and
    surfaces at query time instead. That was confirmed against the real
    driver during Prompt 060 across five malformed inputs, which is why
    this function's own try/except is defensive rather than a path a bad
    setting reaches.
    """
    if not enabled:
        return None
    try:
        return AsyncGraphDatabase.driver(
            settings.uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
            max_connection_pool_size=max_pool_size,
            connection_acquisition_timeout=connection_timeout,
        )
    except Exception as exc:  # pragma: no cover - construction is lazy
        logger.warning(
            "Could not construct the Neo4j driver; GraphRAG will be disabled.",
            extra={"extra_fields": {"error": str(exc)}},
        )
        return None


class GraphClient:
    """Read-only Neo4j access, degrading to empty when unavailable."""

    def __init__(
        self, driver: AsyncDriver | None, *, database: str = "neo4j", enabled: bool = True
    ) -> None:
        self._driver = driver
        self._database = database
        self._enabled = enabled and driver is not None

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def database(self) -> str:
        return self._database

    async def read(
        self,
        cypher: str,
        parameters: dict[str, Any] | None = None,
        *,
        max_records: int = DEFAULT_MAX_RECORDS,
    ) -> list[dict[str, Any]]:
        """Run a read query, returning at most *max_records* rows.

        Never raises on a Neo4j failure. The graph arm of a hybrid search
        contributing nothing is a degraded answer; the whole query
        failing because the graph is down is no answer at all, and the
        other two arms were perfectly capable of answering.
        """
        if not self._enabled or self._driver is None:
            return []
        try:
            async with self._driver.session(database=self._database) as session:
                result = await session.run(cypher, parameters or {})  # type: ignore[arg-type]
                rows: list[dict[str, Any]] = []
                async for record in result:
                    rows.append(dict(record))
                    if len(rows) >= max_records:
                        break
                return rows
        except Exception as exc:
            logger.warning(
                "A graph read failed; the graph arm contributes nothing to this query.",
                extra={"extra_fields": {"error": str(exc)}},
            )
            return []

    async def verify(self) -> bool:
        """Whether the graph is actually reachable right now."""
        if not self._enabled or self._driver is None:
            return False
        try:
            await self._driver.verify_connectivity()
        except Exception as exc:
            logger.warning("Neo4j is not reachable.", extra={"extra_fields": {"error": str(exc)}})
            return False
        return True

    async def close(self) -> None:
        """Release the driver's connection pool."""
        if self._driver is not None:
            await self._driver.close()


__all__ = [
    "DEFAULT_MAX_RECORDS",
    "GraphClient",
    "GraphNode",
    "GraphRelationship",
    "Subgraph",
    "create_driver",
]
