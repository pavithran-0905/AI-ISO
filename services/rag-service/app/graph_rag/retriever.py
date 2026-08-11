"""Graph-augmented retrieval (docs/062 "GRAPHRAG").

**What the graph adds that a vector search cannot.** Vector similarity
answers "what text resembles this question?". A knowledge graph answers
"what is *connected* to the thing this question is about?" -- and those
differ precisely where it matters most operationally. Asked "why is
checkout failing?", vector search returns documents that talk about
checkout failing. Graph expansion returns the services checkout depends
on, whose runbooks never mention checkout at all and are exactly what
somebody needs.

**Entity linking is deliberately conservative.** Matching query terms to
graph nodes by fuzzy similarity would attach an unrelated subgraph to
half the queries in the system, and unrelated context is worse than no
context -- it displaces good chunks from a fixed token budget and gives
a model plausible material to be wrong from. So linking requires an
exact, case-insensitive match on a node key or name.

**Cypher is never built from user input.** Every query here is a fixed
string with bound parameters. The alternative -- interpolating a query
term into a Cypher string -- is injection into a database that has no
concept of a read-only user by default.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from uuid import UUID

from app.graph_rag.client import GraphClient, GraphNode, GraphRelationship, Subgraph

_ANY_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
"""Every word, however short. Used to build multi-word phrases, where a
two-letter word can sit in the middle of a real entity name."""

_MIN_TERM_LENGTH = 3
"""A standalone candidate must be this long. Shorter tokens are almost
always English function words and would link to nothing useful -- but
they are still kept inside phrases, which is why the tokenizer above does
not filter them out."""

_STOPWORDS = frozenset(["the", "and", "for", "with", "from", "that", "this", "what", "why", "how", "when", "where", "which", "who", "does", "are", "was", "were", "will", "would", "should", "could", "have", "has", "had", "been", "being", "not", "but"])

MAX_SEED_ENTITIES = 8
"""How many linked entities seed a traversal. Beyond a handful the
subgraph stops being about the question -- and each seed multiplies the
nodes an expansion can reach."""


MAX_PHRASE_WORDS = 3
"""Longest multi-word candidate considered. Real entity names run to
about three words ("Checkout API", "Payments Service", "Ledger Database
Primary"); beyond that the phrase is a sentence fragment, and generating
longer candidates multiplies the parameter list for matches that never
occur."""


def extract_terms(text: str) -> list[str]:
    """Candidate entity mentions in a query, in order, deduplicated.

    Yields single words **and adjacent phrases up to three words long**.
    Single words alone would only ever link entities whose name is one
    token, and most are not -- "Payments Service" and "Checkout API" are
    the ordinary shape of a name in a real graph. Phrases are built from
    consecutive words only, so no reordering or fuzziness creeps in and
    the match stays exact.

    Stopwords are dropped from unigrams but kept *inside* phrases: an
    entity legitimately named "Bank of England" would be unfindable if
    "of" were removed from the middle of it.
    """
    # Phrases are built from EVERY word, including the short ones the
    # unigram rule discards. "Bank of England" would otherwise become
    # "bank england" -- a phrase that matches nothing, produced by
    # dropping a word from the middle of a name.
    words = [match.group().lower() for match in _ANY_WORD.finditer(text)]
    seen: dict[str, None] = {}
    for word in words:
        if len(word) >= _MIN_TERM_LENGTH and word not in _STOPWORDS:
            seen.setdefault(word, None)
    for size in range(2, MAX_PHRASE_WORDS + 1):
        for start in range(len(words) - size + 1):
            seen.setdefault(" ".join(words[start : start + size]), None)
    return list(seen)


class GraphRetriever:
    """Links a query to graph nodes and expands their neighbourhood."""

    def __init__(
        self,
        client: GraphClient,
        *,
        node_label: str = "GraphNode",
        max_depth: int = 2,
        max_nodes: int = 100,
    ) -> None:
        self._client = client
        self._label = _validate_label(node_label)
        self._max_depth = max(1, min(max_depth, 6))
        self._max_nodes = max(1, max_nodes)

    @property
    def enabled(self) -> bool:
        return self._client.enabled

    async def link_entities(
        self, query: str, organization_id: UUID, *, limit: int = MAX_SEED_ENTITIES
    ) -> list[GraphNode]:
        """Find graph nodes the query explicitly names.

        Exact, case-insensitive match on ``key`` or ``name``. See this
        module's docstring for why fuzzy matching is refused.
        """
        terms = extract_terms(query)
        if not terms or not self._client.enabled:
            return []

        rows = await self._client.read(
            f"MATCH (n:`{self._label}`) "
            "WHERE n.organization_id = $org "
            "AND (toLower(n.key) IN $terms OR toLower(coalesce(n.name, '')) IN $terms) "
            "RETURN n.key AS key, labels(n) AS labels, properties(n) AS props "
            "LIMIT $limit",
            {"org": str(organization_id), "terms": terms, "limit": limit},
            max_records=limit,
        )
        return [_to_node(row) for row in rows]

    async def expand(
        self,
        seeds: Sequence[GraphNode],
        organization_id: UUID,
        *,
        depth: int | None = None,
        relationship_types: Sequence[str] = (),
    ) -> Subgraph:
        """Everything reachable from *seeds* within *depth* hops.

        The depth bound is not a performance tweak. Past two hops a
        knowledge graph of any size returns most of itself, which is the
        opposite of retrieval -- the subgraph stops being about the
        question and becomes a description of the whole estate.
        """
        # Validated BEFORE the early return, so a malformed relationship
        # type is rejected whether or not the graph happens to be enabled.
        # Deferring it means a misconfiguration is silent in every
        # deployment without a graph and raises the day one is turned on.
        types = _validate_relationship_types(relationship_types)
        if not seeds or not self._client.enabled:
            return Subgraph()

        hops = self._max_depth if depth is None else max(1, min(depth, self._max_depth))
        keys = [node.key for node in seeds]
        # The relationship-type filter is part of the pattern, which
        # Cypher cannot parameterise -- hence the strict validation above
        # rather than a bound parameter.
        pattern = f"[r{types}*1..{hops}]"

        rows = await self._client.read(
            f"MATCH (seed:`{self._label}`)-{pattern}-(reached:`{self._label}`) "
            "WHERE seed.key IN $keys AND seed.organization_id = $org "
            "AND reached.organization_id = $org "
            "RETURN DISTINCT reached.key AS key, labels(reached) AS labels, "
            "properties(reached) AS props "
            "LIMIT $limit",
            {"keys": keys, "org": str(organization_id), "limit": self._max_nodes},
            max_records=self._max_nodes,
        )
        nodes = [_to_node(row) for row in rows]

        edges = await self._relationships(keys, organization_id, hops=hops, types=types)
        return Subgraph(
            nodes=nodes,
            relationships=edges,
            truncated=len(nodes) >= self._max_nodes,
        )

    async def _relationships(
        self, keys: Sequence[str], organization_id: UUID, *, hops: int, types: str
    ) -> list[GraphRelationship]:
        """The edges among the expanded neighbourhood.

        Fetched separately from the nodes because a path query returning
        both multiplies rows by path length, and the same edge appears
        once per path that traverses it.
        """
        rows = await self._client.read(
            f"MATCH (seed:`{self._label}`)-[r{types}*1..{hops}]-(:`{self._label}`) "
            "WHERE seed.key IN $keys AND seed.organization_id = $org "
            "UNWIND r AS edge "
            "RETURN DISTINCT type(edge) AS type, "
            "startNode(edge).key AS start_key, endNode(edge).key AS end_key "
            "LIMIT $limit",
            {"keys": keys, "org": str(organization_id), "limit": self._max_nodes},
            max_records=self._max_nodes,
        )
        return [
            GraphRelationship(
                type=str(row.get("type", "")),
                start_key=str(row.get("start_key", "")),
                end_key=str(row.get("end_key", "")),
            )
            for row in rows
            if row.get("start_key") and row.get("end_key")
        ]

    async def retrieve(
        self,
        query: str,
        organization_id: UUID,
        *,
        depth: int | None = None,
        relationship_types: Sequence[str] = (),
    ) -> Subgraph:
        """Link and expand in one call -- the graph arm of hybrid search.

        Returns an empty subgraph when GraphRAG is disabled, when the
        query names nothing in the graph, or when Neo4j is unreachable.
        All three are normal, and none of them is an error: the vector
        and keyword arms answer the query on their own.
        """
        seeds = await self.link_entities(query, organization_id)
        if not seeds:
            return Subgraph()
        expanded = await self.expand(
            seeds, organization_id, depth=depth, relationship_types=relationship_types
        )
        # The seeds themselves belong in the result: the node the query
        # named is usually the most relevant one, and an expansion that
        # returned only its neighbours would omit it.
        known = {node.key for node in expanded.nodes}
        expanded.nodes = [
            *seeds,
            *(n for n in expanded.nodes if n.key not in {s.key for s in seeds}),
        ]
        return expanded


_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validate_label(label: str) -> str:
    """Reject a node label that is not a bare identifier.

    A label cannot be a bound parameter in Cypher -- it is part of the
    pattern -- so it is interpolated, and interpolation demands
    validation. This one comes from configuration rather than a request,
    but a config value is still not a safe thing to concatenate into a
    query language unchecked.
    """
    if not _SAFE_IDENTIFIER.match(label):
        raise ValueError(
            f"Node label {label!r} is not a bare identifier. Labels are "
            "interpolated into Cypher because the language cannot parameterise "
            "them, so anything else is refused."
        )
    return label


def _validate_relationship_types(types: Sequence[str]) -> str:
    """Render a relationship-type filter, or an empty string.

    Same reasoning as :func:`_validate_label`: relationship types are
    part of the pattern and cannot be bound.
    """
    if not types:
        return ""
    for name in types:
        if not _SAFE_IDENTIFIER.match(name):
            raise ValueError(
                f"Relationship type {name!r} is not a bare identifier; refused "
                "because it is interpolated into the Cypher pattern."
            )
    return ":" + "|".join(types)


def _to_node(row: dict[str, object]) -> GraphNode:
    """Build a :class:`GraphNode` from one Cypher row."""
    labels = row.get("labels")
    props = row.get("props")
    return GraphNode(
        key=str(row.get("key", "")),
        labels=tuple(str(label) for label in labels) if isinstance(labels, list) else (),
        properties=dict(props) if isinstance(props, dict) else {},
    )


__all__ = ["MAX_SEED_ENTITIES", "GraphRetriever", "extract_terms"]
