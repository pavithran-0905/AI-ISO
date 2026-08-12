# Document Intelligence Service

Turns documents into structured, scored, reviewable data. Fourteen formats
in; text, layout, categories, entities, tables, form fields, summaries,
translations and validation findings out — each carrying a confidence and a
rationale, and each routable to a human when the confidence is not good
enough.

Implements `docs/063_Enterprise_Document_Intelligence_Service.md`.

- **Port** 8034 · **Database** `aiios_document_intelligence` · **Redis db** 36
- **Object store** MinIO bucket `aiios-documents`

---

## The three ideas that shape everything here

**A confidence score only matters if something acts on it.** Every
extraction carries one, and a document below
`review_required_below_confidence` (0.7 by default) is routed to a human
rather than accepted. A service that computes confidences and then treats
every document identically has measured nothing.

**An unmeasured thing is `None`, never zero.** A window nobody reviewed has
no correction rate; a document nothing scored has no confidence; a page
whose OCR failed has no text *and says so*. Reporting 0.0 for "unmeasured"
reads as a perfect extractor, and it is the most misleading number this
service could produce.

**A failure is data.** One stage failing does not fail the document, one
unreadable page does not fail the scan, and a document that could not be
read is never returned as a document that was read and found empty. Every
degradation is recorded on the thing it happened to.

---

## What it does

### Ingestion and formats

Fourteen formats: PDF, DOCX, XLSX, TXT, Markdown, HTML, RTF, CSV/TSV,
JSON, XML, YAML, images, TIFF and ZIP archives.

Format detection weighs **magic bytes over declared content type over file
extension** — a `.txt` holding a PDF signature is a PDF that was renamed,
and the extension is the one piece of evidence any uploader can set to
anything. DOCX, XLSX and ZIP all share the zip signature and are separated
by the entry names inside the archive. Detection can return `UNKNOWN`, which
is a real answer: guessing `TXT` hands the caller mojibake that looks like a
successful parse.

Original bytes go to MinIO **before the processing job is queued**, so a
worker can never claim a job whose bytes are not yet readable.

A duplicate upload is recorded, not rejected: the same bytes twice is
usually a person re-sending. The second document is stored, linked through
`duplicate_of_id`, and skips reprocessing. Duplicate detection is scoped per
organization — two tenants uploading the same public standard are not
duplicates of each other, and telling one that its document already exists
would leak that the other has it.

### The pipeline

Eight stages in **enforced dependency order**, with parsing prepended
whenever anything else is requested:

```
parsing → ocr → layout → entity_extraction → table_extraction
        → form_extraction → classification → validation_rules
```

Classification runs *after* form extraction, which reads backwards until you
look at what template matching needs: the form's field labels. Form
extraction finds those without knowing the document's category, so with
classification first, template matching silently never fires.

A run records `COMPLETED`, `PARTIAL` or `FAILED`. `PARTIAL` exists because a
document whose tables failed but whose text, entities and classification all
landed is neither a success nor a failure, and a re-run decision needs the
difference. Only a **parse** failure stops the run — every later stage reads
what parsing produced.

### The engines

| Engine | What it does | Worth knowing |
|---|---|---|
| **OCR** | Tesseract, per-word confidence | Reports the **lowest page** confidence beside the mean: a forty-page scan averaging 0.92 with one page at 0.31 hides that page behind the mean |
| **Layout** | Titles, headings, paragraphs, tables, captions, signatures, page numbers, columns | Reading order is column → top → left; repeated boilerplate is dropped when merging pages |
| **Classification** | Rule, template, keyword and structure, fused | Multi-label by default; every label carries its rationale and matched terms |
| **Entities** | 13 kinds plus tenant-defined patterns | A configured pattern outranks the built-in guess on the same span |
| **Tables** | Pipe grids, whitespace-aligned blocks, positioned OCR words | Ragged rows padded and reported; merged cells flagged, never silently flattened |
| **Forms** | Fields, checkboxes, signatures, templates, per-field rules | A blank field is a finding, not a gap: `Signature: ______` and no signature line are different states |
| **Summarization** | Six kinds over one extractive ranker | Every summary is extractive, so it can be wrong about emphasis but never about fact |
| **Translation** | Detection, glossary, terminology preservation | With no backend it **refuses** rather than storing the source labelled as a translation |
| **Validation** | Seven rule kinds, duplicates by word shingles | A rule that could not run records `SKIPPED`, never `PASSED` |

### Human review

Open, assign, start, complete, escalate, and an overdue sweep.

A reviewer's correction is stored **beside** the extraction, never over it.
The original is what the extractor produced and the corrected value is what
a human says it should be; keeping both is the only way to measure how often
the extractor is wrong, which is the whole point of having reviewers.

A completed review never reopens — it is a decision a person made at a time,
and mutating it would rewrite the audit trail. Further work opens a new one.

### Analytics and reports

Hourly statistics windows, **idempotent per window**: a worker running twice
for one window updates the row rather than adding a second that
double-counts every document in it. Seven report kinds in JSON, CSV,
Markdown and HTML — HTML escapes every value, since report content includes
document titles that came from user-chosen filenames.

---

## API

Fifteen endpoints from the spec plus five more. Static segments are
registered **before** the `{document_id}` catch-all: FastAPI matches in
declaration order, so `/documents/statistics` declared after
`/documents/{document_id}` is never reached.

| Method | Path | |
|---|---|---|
| GET | `/documents` | list, filter by status, search, review queue |
| POST | `/documents` | upload (multipart) |
| GET | `/documents/statistics` | recent windows, optional refresh |
| POST | `/documents/statistics/rollup` | force a rollup — **administrators only** |
| GET / POST | `/documents/reports` | list / generate |
| GET | `/documents/{id}` | one document |
| PUT | `/documents/{id}` | editable metadata only |
| DELETE | `/documents/{id}` | soft delete |
| POST | `/documents/{id}/ocr` | re-read with OCR |
| POST | `/documents/{id}/classify` | re-classify (runs form extraction alongside) |
| POST | `/documents/{id}/extract` | run the extraction stages |
| GET | `/documents/{id}/extraction` | everything extracted |
| POST | `/documents/{id}/summarize` | summaries by kind |
| POST | `/documents/{id}/translate` | translations |
| GET | `/documents/{id}/language` | detected language |
| POST | `/documents/{id}/validate` | re-validate |
| POST | `/documents/{id}/review` | open a review |
| GET | `/documents/{id}/reviews` | a document's reviews |
| POST | `/documents/{id}/review/{review_id}/decision` | close a review |

Plus `/health`, `/liveness`, `/readiness`, `/metrics`, `/docs`.

**No endpoint accepts an organization id.** It comes from the caller's
verified token and nowhere else — every repository scopes on the value it is
handed, so a caller supplying somebody else's organization would be served
their documents. Request bodies use `extra="forbid"`, so a client sending
`organization_id` gets a clear rejection rather than silently operating on
its own tenant while believing it named another.

Cross-tenant reads return **404, not 403**: whether a document exists is
itself information.

---

## Events

Nine, all registered with the shared registry at import time — an
unregistered event is an `AIIOS-EVENT-0002` on the request that triggered
it, not a warning.

`DocumentUploaded` · `OCRCompleted` · `ClassificationCompleted` ·
`ExtractionCompleted` · `ValidationCompleted` · `ReviewCompleted` ·
`DocumentArchived` · `ProcessingFailed` · `DocumentDeleted`

The last two are not in the spec's list and are deliberate. Without
`ProcessingFailed`, every other event announces a success, so a consumer
tracking a document sees `DocumentUploaded` and then silence — which is
indistinguishable from a slow queue. Without `DocumentDeleted`, a consumer
maintaining its own index keeps serving links to documents that no longer
exist.

**Payloads carry identifiers and counts, never document content.** This
service exists to find passport numbers and account details; a message bus,
its subscriber queues and its dead-letter store all have different retention
and access rules than this service's database. The same rule governs trace
spans.

---

## Workers

Four, all **leader-elected** through `shared_core.scheduler`, so every
replica starts identically and none needs a flag to be "the worker one".

| Worker | Interval | |
|---|---|---|
| Processing sweep | 30s | claims with `FOR UPDATE SKIP LOCKED`, so two replicas take disjoint work rather than OCRing the same scan twice |
| Review expiry | 15m | **escalates** rather than expires: a review nobody did is a document nobody checked, and `EXPIRED` would drop it out of every open-work query |
| Statistics rollup | 15m | rolls up the hour that has *finished*, never the one in progress |
| Retention sweep | 1h | archives rather than deletes, and **requeues** stalled documents rather than failing them — an interrupted run is not a document defect |

---

## Running it

```bash
# Migrations first, as a separate step -- never in CMD, so a multi-replica
# rollout cannot race two containers running the same migration.
uv run alembic upgrade head

uv run uvicorn main:app --host 0.0.0.0 --port 8034
```

Docker (build context is the repository root, since this service is a member
of the root `uv` workspace):

```bash
docker build -f services/document-intelligence-service/Dockerfile \
  -t aiios/document-intelligence-service:0.1.0 .
```

The image installs `tesseract-ocr`. Without the binary, `pytesseract` is a
wrapper over something that is not there, and every scanned document in
every deployment routes to review with "no OCR engine is configured" — which
looks like a configuration mistake rather than a missing package.

### Configuration

Every setting is prefixed `AIIOS_DOCUMENT_INTELLIGENCE_SERVICE_`. The ones
worth knowing:

| Setting | Default | |
|---|---|---|
| `MAX_DOCUMENT_BYTES` | 52428800 | 50 MB |
| `STORAGE_BUCKET` | `aiios-documents` | original bytes, not extracted text |
| `OCR_ENABLED` | true | probed at startup; unavailable degrades, never crashes |
| `REVIEW_REQUIRED_BELOW_CONFIDENCE` | 0.7 | below this, a human reviews it |
| `DUPLICATE_SIMILARITY_THRESHOLD` | 0.75 | chosen *against* the three-word shingle size — see below |
| `TRANSLATION_ENABLED` | true | with no backend, translation refuses |
| `WORKERS_ENABLED` | true | leader-elected, so leave it on everywhere |

The duplicate threshold and the shingle size have to be chosen together. One
changed word invalidates *k* shingles on each side, so for a document of *S*
shingles the similarity ceiling after a single edit is `(S - k) / (S + k)`.
At five-word shingles that is 0.68 for a thirty-word document — meaning a
re-scan of the same page differing by one OCR error would score below any
sensible threshold and never be flagged, which is the one case
near-duplicate detection exists for. Three-word shingles put the same
re-scan around 0.81, and two different forms sharing a template around 0.12.

---

## Tests

```bash
uv run pytest tests/ --cov=app          # 445 tests, 95.28% coverage
```

Real PostgreSQL, Redis, RabbitMQ and MinIO throughout. **Nothing is mocked
except the Tesseract binary itself**, which a CI machine may not carry — and
that stand-in replaces the third-party wrapper, never this service's own
code, so the engine's parsing, confidence maths, quality banding and error
handling all run for real.

Every test works inside a fresh organization, which makes every test
incidentally a tenant-isolation test: a query that forgot its
`organization_id` filter would see the other tests' rows.

**The one thing the HTTP tests cannot tell you.** The `app` fixture
overrides only the request session, so a test's writes roll back. That
changes *transaction lifetime*, which means behaviour whose correctness
depends on transaction lifetime is untestable through it — notably
`FOR UPDATE SKIP LOCKED` job claiming, which is why the worker ticks run
against the real session factory instead.

---

## Deliberately not implemented

Per the spec's own DO NOT IMPLEMENT list, and each with a reason rather than
an omission:

- **No trained document classifier.** The spec rules out business-specific
  document templates, which is most of what such a model encodes — and a
  classifier whose decisions cannot be explained to the person overriding
  them is one they stop trusting. Rules, templates, weighted keywords and
  structure are all auditable and give the same answer twice. The `AI`
  method is declared in `ClassificationMethod` as the seam.
- **No abstractive summarizer.** `AbstractiveBackend` is the seam; with none
  configured, an abstractive request falls back to extraction and *says so*
  in `fallback_used` rather than returning invented text.
- **No translation backend.** `TranslationBackend` is the seam. With none,
  translation raises — there is no honest degraded translation, and
  returning the source would store English as the French version with
  nothing downstream able to tell.
- **No PDF rasterisation.** OCR over a PDF needs a rasteriser, which is a
  further system dependency this image does not carry. The engine says
  exactly that rather than returning empty pages.
