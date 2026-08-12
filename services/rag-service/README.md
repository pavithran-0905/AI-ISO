# AI-IOS RAG Service

Retrieval-Augmented Generation for the AI-IOS platform (docs/062). Turns
documents into a searchable, access-controlled, citable corpus: parse,
chunk, embed, index, retrieve, rerank, assemble context, and measure how
well any of it worked.

Port **8033**. Redis database **35**. PostgreSQL database **aiios_rag**.

## What it does

| Capability | Where |
|---|---|
| Nine document formats, with provenance | [`app/parsers/`](app/parsers/) |
| Nine chunking strategies | [`app/chunking/`](app/chunking/) |
| Embeddings, with a credential-free builtin encoder | [`app/embeddings/`](app/embeddings/) |
| Pluggable vector stores (pgvector, memory) | [`app/vector_store/`](app/vector_store/) |
| BM25 + reciprocal rank fusion | [`app/hybrid_search/`](app/hybrid_search/) |
| Six reranking methods | [`app/reranking/engine.py`](app/reranking/engine.py) |
| GraphRAG expansion over Neo4j | [`app/graph_rag/`](app/graph_rag/) |
| Token-budgeted context with citations | [`app/context/assembler.py`](app/context/assembler.py) |
| Eight retrieval-quality metrics | [`app/evaluation/metrics.py`](app/evaluation/metrics.py) |
| Ingestion security scanning | [`app/security/scanner.py`](app/security/scanner.py) |
| Classification / role / project access control | [`app/security/access.py`](app/security/access.py) |

## The decisions worth knowing

**Chunking is the single choice that most determines retrieval quality,**
and it is made once at ingestion and then baked into every vector. A chunk
that splits a sentence embeds a fragment whose meaning is neither
sentence's; a chunk that swallows five sections embeds an average of five
topics and is close to none. Neither failure is visible in the vectors —
they surface much later as retrieval that is subtly, unaccountably bad.
Every strategy in `app/chunking/` is therefore a pure function with no
model call and no I/O, so a regression in one is detectable.

**Chunking runs over parsed blocks, not over flattened text.** Every
parser emits blocks carrying where their text came from — page number,
heading trail, whether it was a table. The markdown parser strips `##`
markers, so a heading strategy run over the joined string finds no
headings at all and silently degrades to fixed-size windows; a PDF chunk's
page number becomes permanently unknowable. Citations would then point at
a document rather than into it.

**Nothing is embedded twice.** Each vector records the hash of the text it
came from, and a chunk whose text is unchanged is skipped — even across a
re-ingest, which builds new chunk rows with new ids for byte-identical
paragraphs. Without the content-hash lookup, editing one line of a long
document pays to re-embed all of it. Embedding is the only part of this
service that costs money per call.

**The vector store is the sole writer of vectors and their accounting.**
An earlier split — service writes the accounting row, store writes the
searchable copy — had a hole exactly the size of a failed store call: the
rows landed, the call failed, the document was marked failed, and the next
run saw the rows, skipped everything, and marked the document indexed
while the store held nothing.

**Access filtering happens inside the query, never after it.** Roles,
clearance, and project scope are pushed into the vector search's own WHERE
clause. Retrieving first and hiding the results still leaks through the
result count, the ranking, and the latency, and makes `top_k` mean
different things to different callers. The role filter applies even when
the caller presents no roles at all: skipping it then would show a caller
with no roles every role-restricted document in the organization.

**The organization comes from the token and nowhere else.** Several
earlier AI-IOS services accept it as a request parameter. Here that is a
cross-tenant read — every repository scopes on the value it is handed, and
`can_read` compares the document's organization against the *context's*,
so a caller supplying somebody else's id passes both checks.

**Empty retrievals are the valuable half.** Every query is recorded,
including the ones that found nothing, because that list is the only
output of this service that says what to write next. It depends on a
relevance floor: with none, a vector search always returns its nearest
neighbours, so every query "succeeds". The floor defaults to zero anyway —
the right value depends entirely on the embedding model, and a number
invented here would be wrong for most of them. Operators set it per
deployment (`AIIOS_RAG_SERVICE_MIN_SIMILARITY`).

**`DENIED` is not `EMPTY`.** A query whose only matches were withheld is
answerable by the corpus and unreadable by that caller; the two demand
opposite responses, and only one belongs in the unanswered report.

**Nothing reports a number it does not have.** A window with no feedback
reports `search_accuracy` as `null`, not `0.0`; a metric with nothing to
measure reports itself unmeasurable. One says retrieval is broken, the
other says nobody has looked.

## What is deliberately not implemented

Named rather than stubbed, because a stub that looks finished is worse
than an absence that is stated:

- **Six of the eight vector stores.** Qdrant, Milvus, Weaviate, Chroma,
  Pinecone, and FAISS are declared in `VectorStoreProvider` and refused at
  build time. No instance of any of them exists in this platform's
  infrastructure, so a client would be code that has never executed
  against the thing it claims to talk to. The deliverable is the seam:
  the protocol, the registry, and two real implementations proving it
  holds for both a networked store and an in-process one.
- **Voyage, Cohere, and Gemini embeddings**, for the same reason. OpenAI
  and Azure OpenAI are implemented; the builtin encoder needs no
  credential at all, which is what makes the whole pipeline testable on a
  machine with no API key.
- **Cross-encoder reranking**, which needs a model this service does not
  ship. Refused explicitly — a reranker that quietly did nothing is
  indistinguishable from a working one.
- **OCR**, exposed as `OcrHook` and supplied by the deployment.
- **Source connectors.** Confluence, SharePoint, and S3 fetching is left
  to whoever has an instance to test against;
  `SourceService.record_sync` is the seam they call back into. What is
  real here is the registry, the schedule, the credential *reference*,
  and the per-source ingestion defaults.

## Endpoints

The thirteen docs/062 names, plus the supporting routes they imply:

```
POST   /rag/documents                        GET    /rag/documents
GET    /rag/documents/search                 GET    /rag/documents/{id}
PUT    /rag/documents/{id}                   DELETE /rag/documents/{id}
GET    /rag/documents/{id}/content           GET    /rag/documents/{id}/chunks
POST   /rag/documents/{id}/restore
POST   /rag/index                            POST   /rag/reindex
GET    /rag/index/jobs
POST   /rag/search                           POST   /rag/retrieve
POST   /rag/context
POST   /rag/retrieve/{id}/feedback           GET    /rag/retrieve/{id}/evaluation
GET    /rag/sources                          POST   /rag/sources
GET    /rag/sources/{id}                     PUT    /rag/sources/{id}
DELETE /rag/sources/{id}                     POST   /rag/sources/{id}/sync
GET    /rag/statistics                       GET    /rag/statistics/evaluation
GET    /rag/reports                          POST   /rag/reports
GET    /rag/audit
GET    /health   /liveness   /readiness   /metrics   /docs
```

Every route authenticates, including the read-only ones: retrieval reads
across a corpus the caller has never seen, so an unauthenticated search
endpoint is a corpus-wide disclosure with a nice JSON envelope.

## Background jobs

Four, all leader-elected through `shared_core.scheduler` — each is pure
database work with no per-replica state, and two replicas running the same
indexing job would embed its documents twice and be billed twice.

| Job | Default interval |
|---|---|
| Indexing sweep (runs due jobs, reclaims abandoned ones) | 30s |
| Knowledge-source sync sweep | 900s |
| Document expiry sweep (archives, never deletes) | 3600s |
| Statistics rollup | 900s |

## Running it

```bash
uv sync
uv run alembic upgrade head
uv run uvicorn main:app --host 0.0.0.0 --port 8033
```

```bash
docker build -f services/rag-service/Dockerfile -t aiios/rag-service:0.1.0 .
```

The build context must be the repository root: this service is a member of
the root `uv` workspace and depends on `packages/shared-core` as a
workspace path dependency.

## Tests

```bash
uv run python -m pytest tests/ --cov=app
```

577 tests against **real** PostgreSQL with pgvector, Redis, and RabbitMQ.
Nothing is mocked: the vectors are real vectors in a real `vector(1536)`
column and the searches are real pgvector searches. The suite needs no
model-provider credential, because the builtin encoder needs none — a RAG
service whose tests only run when somebody has an OpenAI key is a RAG
service whose tests do not run.

Coverage is **92%** against a 95% target. What remains uncovered is
concentrated in defensive branches: the worker-registration path in
`app/core/factory.py` (reachable only with `workers_enabled=true` and a
live scheduler), the Neo4j-backed halves of `app/graph_rag/`, and
error paths in the format parsers.
