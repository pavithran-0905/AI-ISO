# Developer Portal Service

Enterprise Developer Portal Service (Prompt 074) — the developer-facing
front door: onboarding, documentation, interactive API/GraphQL
exploration, webhook testing, SDK distribution, sample projects, code
playground, learning center, plugin publishing, an AI documentation
assistant, search, and community.

Port `8045`. Database `aiios_developer_portal`. Redis db `47`.

## Ideas that shape everything here

**This service owns the portal experience, not the underlying
capability.** `app/documentation/engine.py`'s `ContentStatus`
DRAFT/PUBLISHED/ARCHIVED transition table is reused, unmodified, by
four services — `DocumentationPageService`, `TutorialService`,
`SampleProjectService`, and `KnowledgeArticleService` — one state
machine, not four copies, mirroring
`services/public-api-platform`'s own "shared credential lifecycle"
precedent (Prompt 073).

**No AI-IOS service in this codebase calls another over live HTTP** —
reconfirmed here. The AI Documentation Assistant (docs/074 names it as
integrating Prompt 060 AI Agent Platform + Prompt 062 RAG Service) is
implemented as a self-contained heuristic keyword-overlap matcher
(`app/assistant/engine.py`, reusing `app/search/engine.py`'s scoring)
rather than a live cross-service call. Every cross-service
"integration" claimed by a docs/0xx spec in this build has turned out
to be either an event/notification wiring or a reused conceptual
pattern, never a runtime HTTP dependency.

**Search is a declared seam.** docs/074's own "DO NOT IMPLEMENT" list
excludes External Search Engines — `app/search/engine.py`'s
deterministic keyword-overlap scoring (title × 3, keywords × 2, summary
× 1, normalized by query length) stands in for a live
Elasticsearch/OpenSearch or vector-embedding search. `SearchIndexEntry`
is this service's own materialized index, rebuilt from current
published content by `SearchIndexRebuildWorker`.

**Tutorial/AI-assistant completion tracking has no persisted table at
all.** docs/074's own DATABASE TABLES section (24 tables, authoritative)
names no per-user completion-tracking table despite "Progress Tracking"
being called out under LEARNING CENTER. `TutorialCompletedEvent` and
`AIAssistantUsedEvent` are published on a caller's own report/action,
but nothing writes a row when they fire — documented in
`app/tutorials/engine.py`'s own module docstring, and reconfirmed by
`app.workers.statistics_rollup`'s own "honest zero" counters below.

**"Honest zero" counters, continued.** Four of `PortalStatistic`'s
eight counters (`documentation_view_count`, `search_query_count`,
`tutorial_completion_count`, `ai_assistant_usage_count`) are always
`0` — this service never had a page-view or search-query log table to
begin with, and completion/assistant-usage events fire without a
backing row (see above). Reported as real zeros, not omitted, matching
the pattern established in Prompt 071 (`auth_failure_count`) and
continued through 072/073.

**Eight notification kinds, three dispatch shapes.** One is fanned from
a domain event (`DocumentationPublished` → Documentation Updated, via
`NotifyingPublisher`); six are called directly by the code that
observes the underlying fact (SDK Released, Plugin Approved, Plugin
Rejected, Tutorial Available, AI Recommendation, Community Reply); one
(Security Notice) is a declared seam — this service owns no
security-event detection of its own, so nothing internal calls it, but
it is directly tested like every other kind, the same shape
`services/public-api-platform`'s Webhook Failure notification took.

**A webhook test never makes an outbound call from inside a request
handler.** `WebhookTestService.record_result` records an outcome the
caller already observed — the same caller-reported-outcome pattern
this codebase uses everywhere a service must not itself reach out to
an arbitrary developer-supplied URL.

## A repository-misuse bug class found and fixed three times

Beyond the two well-known lesson classes (reserved column names,
enum `is`/`==`/`.value` safety — both checked proactively throughout
this build, with zero new instances found), this build surfaced a
**new** bug class, caught by self-review before any test was written:

Misusing an existing narrowly-scoped repository method (typically
`list_for_user`) with degenerate arguments (`user_id=""`, `limit=0`)
as if it meant "list everything for this organization." Every
occurrence silently returned an empty result rather than raising:

1. `SdkDownloadService.record()`'s first-sighting check
   (`list_for_user(org, user_id="")`) always returned empty, so
   `notify_sdk_released` fired on *every* download instead of only the
   first. Fixed with a dedicated `SdkDownloadRepository.exists_for_version`.
2. `SearchIndexRebuildWorker`'s organization discovery only checked
   `search_index`/`plugin_submissions`, so an organization whose only
   activity was publishing documentation would never be indexed on a
   first rebuild. Fixed by adding `list_organization_ids()` to all four
   content repositories and unioning five sources — regression-tested
   in `tests/test_workers.py::test_org_discovered_purely_from_documentation_is_indexed`.
3. `StatisticsRollupWorker`'s `sdk_download_count` used
   `list_for_user(org, user_id="", limit=0)` — both the empty
   `user_id` *and* `limit=0` guaranteed an always-empty result. Fixed
   with `SdkDownloadRepository.list_since` — regression-tested in
   `tests/test_workers.py::test_sdk_download_count_reflects_real_activity`.

## Architecture

- `app/models/` — 24 tables across 10 files: `developers.py`
  (DeveloperProfile, DeveloperSession, DeveloperBookmark,
  DeveloperFavorite), `documentation.py` (DocumentationPage,
  DocumentationVersion, DocumentationFeedback), `learning.py`
  (Tutorial, LearningPath), `samples.py` (SampleProject, CodeSnippet),
  `explorer.py` (PlaygroundSession, GraphQlQuery, WebhookTest),
  `sdk.py` (SdkDownload — the portal's own download-experience record,
  distinct from `services/sdk-cli-service`'s own `sdk_downloads`
  table), `plugins.py` (PluginSubmission, PluginReview),
  `community.py` (CommunityPost, CommunityComment), `knowledge.py`
  (KnowledgeArticle, SearchIndexEntry), `reporting.py`
  (PortalStatistic, PortalReport, PortalAudit).
- 10 pure engines, each hand-verified before any pytest was written
  (37 checks, zero defects): `app/documentation/engine.py` (the shared
  `ContentStatus` transition table, reused by 4 services),
  `app/portal/engine.py` (session expiry), `app/playground/engine.py`
  (idle-session staleness), `app/explorer/engine.py` (constant-time
  webhook signatures, response classification, minimal GraphQL
  well-formedness check), `app/plugins/engine.py` (submission
  lifecycle with a resubmission path from `REJECTED`, checksum
  round-trip), `app/community/engine.py` (post lifecycle, reputation
  scoring), `app/search/engine.py` (weighted keyword-overlap ranking),
  `app/assistant/engine.py` (confidence-gated answer selection reusing
  the search engine), `app/tutorials/engine.py` (estimated-duration
  summation, difficulty-progression sanity check),
  `app/analytics/engine.py` (engagement rate, growth rate).
- `app/services/` — one service per table-group plus
  `notifications.py` (`PortalNotifier` + `NotifyingPublisher`),
  `audit.py` (the single write path for `portal_audit`), `bundle.py`
  (the shared repository bundle).
- `app/api/portal.py` — the 12 REST routes exactly as docs/074 lists
  them, tenant always derived from the token, never a parameter.
- `app/workers/` — 5 leader-elected background jobs: developer session
  expiry sweep, playground session expiry sweep, search index rebuild,
  statistics rollup, plugin submission staleness sweep (auto-rejects a
  submission stuck in `VALIDATING` past its own configured maximum
  age).
- 9 domain events (`app/events/domain_events.py`), 8 notification
  kinds (`app/services/notifications.py`) — 1 fanned from an event, 6
  called directly, 1 a declared seam.

## Testing

145 tests (42 engine, 25 repository, 34 service, 8 worker, 13 API, 21
deps/notifications/registrar, plus 2 smoke tests) at 97.56% coverage,
against real PostgreSQL and Redis. Ruff, Black, and MyPy (scoped to
`app/` + `main.py`) all clean.

Live Docker e2e confirmed: all 5 workers registered and leader-elected
on startup; health/readiness real; the full plugin-submission →
community-post lifecycle exercised end-to-end through real HTTP
against the running container with a real RS256-signed JWT; **the
plugin submission staleness sweep worker confirmed to autonomously
reject a manually-backdated `VALIDATING` submission on its very next
scheduled tick** — watched directly via `psql` and the worker's own
structured logs (`reviewer_id: "system:plugin-submission-staleness-sweep"`),
never manually triggered; the statistics rollup worker confirmed to
roll up the active organization on its own schedule; RBAC confirmed
(403 non-admin on `/portal/statistics`, 401 no token on `/portal/home`);
database truncated and container removed after.
