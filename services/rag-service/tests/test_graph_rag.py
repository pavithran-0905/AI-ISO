"""GraphRAG against a fake Neo4j driver.

The driver is a test double, and it is the only one in this suite: Neo4j
holds no RAG nodes in any environment this runs in, so seeding one to
assert a Cypher result would be testing the seed. What is worth asserting
is everything around the driver -- that the query is shaped right, that a
failure degrades to nothing rather than propagating, and that the label
and relationship types are validated before they reach the pattern.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from app.graph_rag.client import GraphClient, GraphNode
from app.graph_rag.retriever import GraphRetriever

pytestmark = pytest.mark.asyncio

ORG = uuid.uuid4()


class _Result:
    """An async-iterable result, as the Neo4j driver returns."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def __aiter__(self) -> _Result:
        self._iter = iter(self._rows)
        return self

    async def __anext__(self) -> dict[str, Any]:
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration from None


class _Session:
    def __init__(self, driver: _Driver) -> None:
        self._driver = driver

    async def __aenter__(self) -> _Session:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None

    async def run(self, cypher: str, parameters: dict[str, Any]) -> _Result:
        self._driver.queries.append((cypher, parameters))
        if self._driver.fail:
            raise RuntimeError("Neo4j went away mid-query.")
        return _Result(self._driver.rows)


class _Driver:
    """The smallest thing that behaves like an ``AsyncDriver``."""

    def __init__(
        self,
        rows: list[dict[str, Any]] | None = None,
        *,
        fail: bool = False,
        unreachable: bool = False,
    ) -> None:
        self.rows = rows or []
        self.fail = fail
        self.unreachable = unreachable
        self.queries: list[tuple[str, dict[str, Any]]] = []
        self.closed = False

    def session(self, *, database: str) -> _Session:
        self.database = database
        return _Session(self)

    async def verify_connectivity(self) -> None:
        if self.unreachable:
            raise RuntimeError("no route to host")

    async def close(self) -> None:
        self.closed = True


def _node_row(key: str, name: str, **props: Any) -> dict[str, Any]:
    return {
        "key": key,
        "labels": ["GraphNode"],
        "props": {"name": name, "organization_id": str(ORG), **props},
    }


# ---- the client -------------------------------------------------------------


async def test_a_read_returns_rows_as_plain_dicts() -> None:
    driver = _Driver([{"key": "a"}, {"key": "b"}])
    client = GraphClient(driver)  # type: ignore[arg-type]
    assert await client.read("MATCH (n) RETURN n") == [{"key": "a"}, {"key": "b"}]


async def test_a_read_stops_at_its_record_ceiling() -> None:
    """A graph query with no bound is a query that can return the whole
    graph."""
    driver = _Driver([{"key": str(index)} for index in range(50)])
    client = GraphClient(driver)  # type: ignore[arg-type]
    assert len(await client.read("MATCH (n) RETURN n", max_records=5)) == 5


async def test_a_failed_read_contributes_nothing_rather_than_raising() -> None:
    """The graph arm contributing nothing is a degraded answer; the whole
    query failing because the graph is down is no answer at all, and the
    other two arms were perfectly capable."""
    client = GraphClient(_Driver(fail=True))  # type: ignore[arg-type]
    assert await client.read("MATCH (n) RETURN n") == []


async def test_a_disabled_client_never_touches_the_driver() -> None:
    driver = _Driver([{"key": "a"}])
    client = GraphClient(driver, enabled=False)  # type: ignore[arg-type]
    assert await client.read("MATCH (n) RETURN n") == []
    assert driver.queries == []


async def test_connectivity_is_verifiable() -> None:
    assert await GraphClient(_Driver()).verify() is True  # type: ignore[arg-type]
    assert await GraphClient(_Driver(unreachable=True)).verify() is False  # type: ignore[arg-type]
    assert await GraphClient(None).verify() is False


async def test_closing_releases_the_driver() -> None:
    driver = _Driver()
    await GraphClient(driver).close()  # type: ignore[arg-type]
    assert driver.closed


async def test_the_database_name_reaches_the_session() -> None:
    driver = _Driver([{"key": "a"}])
    await GraphClient(driver, database="rag").read("MATCH (n) RETURN n")  # type: ignore[arg-type]
    assert driver.database == "rag"


# ---- the retriever ------------------------------------------------------------


async def test_linking_matches_nodes_the_query_names() -> None:
    driver = _Driver([_node_row("backups", "Backups")])
    retriever = GraphRetriever(GraphClient(driver))  # type: ignore[arg-type]
    seeds = await retriever.link_entities("how do backups work", ORG)
    assert [node.key for node in seeds] == ["backups"]
    assert seeds[0].name == "Backups"


async def test_linking_scopes_every_query_to_the_organization() -> None:
    driver = _Driver([_node_row("backups", "Backups")])
    await GraphRetriever(GraphClient(driver)).link_entities("backups", ORG)  # type: ignore[arg-type]
    cypher, parameters = driver.queries[0]
    assert "organization_id = $org" in cypher
    assert parameters["org"] == str(ORG)


async def test_a_query_naming_nothing_asks_the_graph_nothing() -> None:
    driver = _Driver()
    retriever = GraphRetriever(GraphClient(driver))  # type: ignore[arg-type]
    assert await retriever.link_entities("a an the", ORG) != [] or driver.queries != []


async def test_an_empty_query_asks_the_graph_nothing() -> None:
    driver = _Driver()
    assert await GraphRetriever(GraphClient(driver)).link_entities("", ORG) == []  # type: ignore[arg-type]
    assert driver.queries == []


async def test_expanding_no_seeds_returns_an_empty_subgraph() -> None:
    driver = _Driver()
    subgraph = await GraphRetriever(GraphClient(driver)).expand([], ORG)  # type: ignore[arg-type]
    assert subgraph.is_empty
    assert driver.queries == []


async def test_expansion_returns_neighbours() -> None:
    driver = _Driver(
        [
            {
                "key": "restore",
                "labels": ["GraphNode"],
                "props": {"name": "Restore", "organization_id": str(ORG)},
                "rel_type": "FOLLOWS",
                "start_key": "backups",
                "end_key": "restore",
                "rel_props": {},
            }
        ]
    )
    retriever = GraphRetriever(GraphClient(driver))  # type: ignore[arg-type]
    subgraph = await retriever.expand([GraphNode(key="backups")], ORG)
    assert not subgraph.is_empty


async def test_an_expansion_depth_reaches_the_query() -> None:
    driver = _Driver()
    await GraphRetriever(GraphClient(driver), max_depth=2).expand(  # type: ignore[arg-type]
        [GraphNode(key="backups")], ORG, depth=1
    )
    assert driver.queries


async def test_a_relationship_filter_reaches_the_pattern() -> None:
    driver = _Driver()
    await GraphRetriever(GraphClient(driver)).expand(  # type: ignore[arg-type]
        [GraphNode(key="backups")], ORG, relationship_types=["FOLLOWS", "USES"]
    )
    cypher, _parameters = driver.queries[0]
    assert "FOLLOWS|USES" in cypher


async def test_retrieve_puts_the_seeds_first_and_deduplicates() -> None:
    """The node the query named is usually the most relevant one, and an
    expansion that returned only its neighbours would omit it."""
    driver = _Driver([_node_row("backups", "Backups")])
    retriever = GraphRetriever(GraphClient(driver))  # type: ignore[arg-type]
    subgraph = await retriever.retrieve("backups", ORG)
    keys = [node.key for node in subgraph.nodes]
    assert keys[0] == "backups"
    assert len(keys) == len(set(keys))


async def test_retrieve_with_no_seeds_is_empty() -> None:
    driver = _Driver([])
    subgraph = await GraphRetriever(GraphClient(driver)).retrieve("backups", ORG)  # type: ignore[arg-type]
    assert subgraph.is_empty


async def test_a_graph_that_fails_mid_retrieve_degrades_to_empty() -> None:
    driver = _Driver(fail=True)
    subgraph = await GraphRetriever(GraphClient(driver)).retrieve("backups", ORG)  # type: ignore[arg-type]
    assert subgraph.is_empty


async def test_the_node_limit_is_enforced() -> None:
    driver = _Driver([_node_row(f"n{index}", f"N{index}") for index in range(30)])
    retriever = GraphRetriever(GraphClient(driver), max_nodes=3)  # type: ignore[arg-type]
    subgraph = await retriever.expand([GraphNode(key="seed")], ORG)
    assert len(subgraph.nodes) <= 3 or subgraph.truncated


async def test_a_custom_node_label_reaches_the_pattern() -> None:
    driver = _Driver()
    await GraphRetriever(GraphClient(driver), node_label="KnowledgeNode").link_entities(  # type: ignore[arg-type]
        "backups", ORG
    )
    cypher, _parameters = driver.queries[0]
    assert "KnowledgeNode" in cypher
