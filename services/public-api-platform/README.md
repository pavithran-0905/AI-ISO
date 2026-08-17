# Public API & Developer Platform

Enterprise Public API & Developer Platform (Prompt 073) — external API
exposure, developer onboarding, application/credential management, API
products/plans/subscriptions, rate limiting, quotas, sandbox, mock
services, SDK publishing integration, governance, and analytics for
partners, customers, ISVs, OEMs, and independent developers.

Port `8044`. Database `aiios_public_api_platform`. Redis db `46`.

## Ideas that shape everything here

**This is not the API Gateway.** docs/073's own "DO NOT IMPLEMENT" list
excludes an API Gateway Proxy Engine, third-party identity providers,
cloud API management products, and external billing systems. This
service manages the *ecosystem* around public APIs — who can call them,
what they're allowed to call, how much they've called, what's published
about them — never the live request-proxying itself (that already
belongs to `services/api-gateway-service`, Prompt 056). Consequently
`api_usage` has no ingestion route either: recording a call is
internal/administrative (mirroring `services/mobile-api-service`'s own
"five tables with no `POST` route" precedent from Prompt 072), read
only via `GET /usage`.

**The caller is a third-party developer, not a platform administrator
— except for two routes.** Of the 15 REST endpoints, 13 are exercised
by an already-authenticated developer acting on their own account
(`POST /developers/register` through `GET /quotas`); only
`GET /statistics` and `GET /reports` (fleet-wide operational views) are
gated behind `require_administrator`. This mirrors
`services/mobile-api-service`'s own departure from the
administrator-heavy routing of 069–071.

**A developer-facing caller is identified by email, not a platform user
id.** Every other AI-IOS service treats a verified token's `sub` claim
as an opaque platform user id; here, for a public developer portal
login flow, `sub` carries the developer's own email address — the
identifier `developer_accounts.email` (unique per tenant) is actually
keyed on. `GET /developers/profile` and every route requiring
`CurrentDeveloper` resolve the caller by looking up that email within
the caller's own token-derived `organization_id`.

**Five tables have no `POST` route at all** (`api_usage`,
`api_rate_limits`, `api_quotas`, `api_sandbox`/`api_mock_services`,
`openapi_documents`/`graphql_schemas`/`api_changelog`) — docs/073's REST
APIs section lists exactly 15 endpoints and none of them create these.
They are administratively authored or internally recorded (their own
service classes have `create`/`record`/`provision`/`publish` methods,
exercised directly by tests and, in a real deployment, by whatever
internal tooling or usage-collection path populates them) and only ever
read over HTTP where a route exists at all — the same pattern
`services/mobile-api-service` and `services/administration-portal-service`
established for their own internal-only tables.

**Quota consumption publishes `QuotaExceeded` exactly once per
breach, not once per over-limit call.** `QuotaService.consume` compares
"was already exceeded" against "is now exceeded" before deciding
whether to publish — a developer who keeps calling after crossing their
own limit does not flood the event bus with a fresh `QuotaExceeded` on
every subsequent call.

**API version lifecycle is strictly linear**: `DRAFT → RELEASED →
DEPRECATED → SUNSET`, with no path backward and no path that skips a
stage — a version cannot be sunset without having been deprecated
first, matching the same "state machine as the source of truth for
what auditing means" discipline every prior lifecycle engine in this
codebase uses. Numeric (never lexical) semantic-version comparison
lives in `app/versioning/engine.py`, reused from
`services/sdk-cli-service`'s own Prompt 071 precedent.

**Sandbox reset is a worker's job, not a route's.** docs/073's SANDBOX
section names "Reset Sandbox" as a first-class capability;
`SandboxResetSweepWorker` is what actually resets a session that has
outlived its own configured maximum age, autonomously — confirmed live
in this build's own Docker e2e run alongside the credential expiry
sweep.

**Webhook Failure notification is a declared seam.** This service does
not own any webhook data — `services/webhook-service` (Prompt 057)
does, and its own retry/analytics loop is where a real webhook-failure
signal originates. `DeveloperNotifier.notify_webhook_failure` exists and
is directly tested like every other notification kind, but nothing
inside this build calls it internally; a full deployment would wire it
to whatever consumes webhook-service's own failure events.

## Two lessons this build re-confirmed

Both of the reserved-name and enum bug classes documented in prior
AI-IOS prompts (067's reserved-column collisions, 066/071's enum
`is`/`==`/`.value` pitfall) were checked proactively, field-by-field,
while designing this service's 23 tables — `ApiVersion.version_label`
was deliberately named to avoid colliding with `BaseEntityMixin`'s
reserved `version` int column, exactly the collision Prompt 071 found
the hard way for `SdkVersion`/`CliVersion`/`CliPlugin`. Every
enum-typed column read in a service or worker goes through
`EnumClass(value)` coercion rather than bare `.value` or `is`. No new
instance of either bug class was found in this build.

## Architecture

- `app/models/` — 23 tables across 8 files: `developers.py`
  (DeveloperAccount, DeveloperOrganization), `applications.py`
  (DeveloperApplication, ApplicationCredential), `products.py`
  (ApiProduct, ApiPlan, ApiSubscription), `credentials.py` (ApiKey,
  PersonalAccessToken, OAuthClient, OAuthToken), `documents.py`
  (ApiVersion, OpenApiDocument, GraphQlSchema, ApiChangelogEntry),
  `usage.py` (ApiUsageEvent, ApiRateLimit, ApiQuota), `sandbox.py`
  (ApiSandboxSession, ApiMockService), `reporting.py`
  (DeveloperStatistic, DeveloperReport, DeveloperAudit).
- 10 pure engines, each hand-verified before any pytest was written
  (58 checks, zero defects): `app/developers/engine.py` (account
  lifecycle — the one AI-IOS lifecycle in this build where a
  non-terminal status can be reinstated), `app/applications/engine.py`
  (application lifecycle), `app/oauth/engine.py` (constant-time PKCE
  verification, token expiry, grant-type membership),
  `app/api_keys/engine.py` (shared credential lifecycle for API keys/
  PATs/application credentials/OAuth secrets), `app/products/engine.py`
  (governance workflow with an explicit rejection path back to
  ``DRAFT``), `app/versioning/engine.py` (numeric semver parsing/
  comparison, breaking-change detection, strictly linear version
  lifecycle), `app/rate_limits/engine.py` (threshold/burst/remaining-
  capacity math), `app/quotas/engine.py` (daily/weekly/monthly period-
  window computation with calendar-correct month arithmetic, exceeded/
  warning checks), `app/sandbox/engine.py` (mock response resolution
  with error-simulation override, session staleness), `app/analytics
  /engine.py` (error rate, average latency, growth rate).
- `app/services/` — one service per table-group plus `notifications.py`
  (`DeveloperNotifier` + `NotifyingPublisher`), `audit.py` (the single
  write path for `developer_audit`), `bundle.py` (the shared repository
  bundle).
- `app/api/public_api.py` — the 15 REST routes exactly as docs/073
  lists them.
- `app/workers/` — 5 leader-elected background jobs: credential expiry
  sweep (API keys, PATs, OAuth tokens), quota reset sweep, API version
  lifecycle sweep, statistics rollup, sandbox reset sweep.
- 8 domain events (`app/events/domain_events.py`), 7 notification kinds
  (`app/services/notifications.py`) — 1 fanned from an event
  (`APIVersionReleased` → API Version Released), 5 called directly by
  the code that observes the underlying fact, 1 a declared seam
  (Webhook Failure).

## Testing

160 tests (54 engine, 27 repository, 26 service, 12 worker, 19 API, 20
deps/notifications/registrar, plus 2 smoke tests) at 96.99% coverage,
against real PostgreSQL and Redis. Ruff, Black, and MyPy (scoped to
`app/` + `main.py`) all clean. Live Docker e2e confirmed: all 5 workers
registered and leader-elected on startup; health/readiness real; the
full developer-registration → application-creation →
credential-issuance lifecycle exercised end-to-end through real HTTP
against the running container; the credential expiry sweep worker
confirmed to autonomously expire a manually-backdated API key on its
very next tick — watched directly via `psql`, never manually
triggered; the statistics rollup worker confirmed to create and then
idempotently update the same window's row on every subsequent tick;
RBAC confirmed (403 non-admin, 401 no token); database truncated and
container removed after.
