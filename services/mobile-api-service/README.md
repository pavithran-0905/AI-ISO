# Mobile API Service

Enterprise Mobile API Service (Prompt 072) — secure mobile authentication,
offline synchronization, push notifications, mobile device management,
QR-code onboarding, deep linking, and mobile application lifecycle support
for Android, iOS, Flutter, React Native, and Progressive Web App clients.

Port `8043`. Database `aiios_mobile_api`. Redis db `45`.

## Ideas that shape everything here

**The caller is the mobile client, not a platform administrator.** Unlike
most AI-IOS services, most of this service's 13 routes are exercised by an
already-authenticated end user's own mobile app — `POST /mobile/login`,
`POST /mobile/register-device`, `GET/PUT /mobile/profile`, `POST
/mobile/sync`, `POST /mobile/push/register`, `POST /mobile/qr/register` all
just need a valid bearer token representing *some* authenticated caller.
Only `GET /mobile/statistics` and `GET /mobile/reports` are fleet-wide
operational views gated behind `require_administrator`.

**This service never mints the platform's own JWT.** Login here means
"register a device, evaluate its trust and integrity, and start a
mobile-scoped session for the caller's already-authenticated identity" — the
caller already holds a valid bearer token issued by
`services/authentication-service` (integration 030) before it ever calls
`POST /mobile/login`. What this service *does* issue is `mobile_tokens`: its
own opaque, SHA-256-hashed, device-bound offline/refresh tokens, entirely
separate from the platform's RS256 identity JWT.

**Enqueue synchronously, process in the background — for both sync and
push.** `POST /mobile/sync` only creates a `MobileSyncJob` and its
`MobileSyncQueueItem` rows (status `QUEUED`) and returns immediately;
draining that queue — applying each item, detecting and resolving
conflicts, retrying, completing or failing the job — is exclusively
`SyncQueueRetrySweepWorker`'s job. Likewise, `PushService.attempt_delivery`
is only ever called from `PushDeliveryRetrySweepWorker`, never from a
route. This mirrors how a real mobile client's own background sync and
push delivery actually work, and — more importantly for this build's own
methodology — it means the worker is not a "sweep leftovers" safety net
but the *primary* processor, which was proven live: a `POST /mobile/sync`
call against the running Docker container left its job `PENDING` and its
queue item `QUEUED`; twelve seconds later, with nothing else touching it,
`SyncQueueRetrySweepWorker`'s own tick picked it up, applied it, and moved
the job to `COMPLETED` — confirmed via `psql`, never manually triggered.

**Conflict detection is honest about what this service can actually
know.** This service does not own the arbitrary downstream AI-IOS
resources a queued offline action ultimately targets — calling out to
whichever service does is a declared-out-of-scope integration. A queued
item's own `payload` may optionally carry a `server_updated_at` ISO-8601
hint (in a full deployment, populated by whatever call the worker would
make to the owning service); when the hint is absent, the item is applied
with no conflict, since there is nothing this service could truthfully
detect a conflict against. The pure conflict-detection and
strategy-resolution engine (`app/sync/engine.py`) is fully implemented and
fully tested regardless — only the "learn the server's real state" half of
the picture is a declared seam.

**Push delivery is a declared seam too.** Actually handing a payload to
Firebase Cloud Messaging or the Apple Push Notification Service is an
external integration this prompt explicitly excludes (native platform
SDKs). What `PushDeliveryRetrySweepWorker` can honestly determine is
whether the target device has a currently usable registered push token —
if it does, the notification is considered handed off (`DELIVERED`); if
not, delivery fails and retries per `is_retry_eligible` until the
configured budget is exhausted, then `FAILED` and `PushFailed` is
published.

**QR tokens live in Redis, not Postgres.** There is no `mobile_qr_tokens`
table among docs/072's fourteen — a one-time, self-expiring credential is
exactly what a cache (through `shared_core.cache.manager.CacheManager`,
per docs/019 "no service shall communicate directly with Redis") is for,
not the system of record. `QrService.redeem` reads then deletes the key in
one call, so a second redemption of the same token finds nothing.

**`MobileAppVersion`, `MobileConfiguration`, `MobileReport`,
`MobileTelemetryEvent`, and `MobileAnalyticsEvent` have no `POST` route.**
docs/072's REST APIs section lists exactly 13 endpoints, and none of them
create these five tables. They are administratively authored / internally
recorded (their own service classes have `create`/`record`/`generate`
methods, exercised directly by tests and in a real deployment by
whatever internal tooling or telemetry-collection path populates them) and
only ever read over HTTP — the same "admin/internal-managed, read-only
over HTTP" pattern `services/administration-portal-service` established
for its own diagnostics tables.

**`GET /mobile/statistics` computes live, not from a rollup table.**
There is no `mobile_statistics` table among the fourteen either — the
window's `daily_active_users`, `session_count`,
`average_session_duration_seconds`, `crash_rate`, `offline_usage_ratio`,
`notification_engagement_rate`, and `sync_success_rate` are all derived
on demand from the raw `mobile_analytics`/`mobile_telemetry` event rows in
`StatisticsService.compute`, using the pure aggregation functions in
`app/analytics/engine.py`.

## Two lessons this build re-confirmed

Both of the reserved-name/enum bug classes documented in prior AI-IOS
prompts (067's reserved-column collisions, 066/071's enum `is`/`==`/`.value`
pitfall) were checked proactively field-by-field while designing this
service's models — `MobileDevice.app_version_label`,
`MobileAppVersion.version_label`, and `MobileConfiguration`'s `key`/`value`
were all deliberately renamed away from anything colliding with
`BaseEntityMixin`'s reserved set (`id`, `created_at`, `updated_at`,
`is_active`, `organization_id`, `project_id`, `version`) before the first
migration was ever generated, and every enum-typed column access in
services/workers goes through `EnumClass(value)` coercion rather than `is`
or bare `.value`. No new instance of either bug class was found in this
build — the discipline established in 071 held.

## Scope boundary

Per docs/072 "DO NOT IMPLEMENT": no native Android SDK, no native iOS SDK,
no mobile UI applications, and no mobile device operating systems are
implemented here. This is the backend platform those clients talk to, not
a client of its own.

## Architecture

- `app/models/` — 14 tables across 6 files: `devices.py` (MobileDevice,
  MobileSession, MobileProfile, MobileToken), `sync.py` (MobileSyncJob,
  MobileSyncQueueItem), `notifications.py` (MobilePushToken,
  MobileNotification), `configuration.py` (MobileAppVersion,
  MobileConfiguration), `telemetry.py` (MobileTelemetryEvent,
  MobileAnalyticsEvent), `reporting.py` (MobileReport, MobileAudit).
- 10 pure engines, each hand-verified before any pytest was written:
  `app/authentication/engine.py` (session expiry/warning windows, offline
  auth eligibility), `app/devices/engine.py` (trust transitions),
  `app/sync/engine.py` (job/queue transitions, conflict detection/
  resolution, retry backoff), `app/push/engine.py` (delivery transitions,
  retry eligibility, token usability), `app/versions/engine.py` (dotted
  version parsing/comparison — numeric, never lexical), `app/configuration
  /engine.py` (scope matching and platform-override resolution),
  `app/qr/engine.py` (token generation/expiry), `app/deep_links/engine.py`
  (build/parse round trip), `app/security/engine.py` (integrity scoring,
  certificate fingerprint format, replay-attack detection),
  `app/analytics/engine.py` (rate/average aggregation math).
- `app/services/` — one service per table-group plus `notifications.py`
  (`MobileNotifier` + `NotifyingPublisher`), `audit.py` (the single write
  path for `mobile_audit`), `bundle.py` (the shared repository bundle).
- `app/api/mobile.py` — the 13 REST routes exactly as docs/072 lists them.
- `app/workers/` — 5 leader-elected background jobs: session expiry sweep,
  token expiry sweep, sync queue retry sweep, push delivery retry sweep,
  app version compliance sweep.
- 9 domain events (`app/events/domain_events.py`), 7 notification kinds
  (`app/services/notifications.py`) — 2 fanned from events
  (`MobileLoginSucceeded` → New Device Login when `is_new_device`,
  `SynchronizationFailed` → Synchronization Failed), 5 called directly by
  the code that observes the underlying fact.

## Testing

218 tests (90 engine, 31 repository, 31 service, 14 worker, 28 API, 22
deps/notifications/registrar, plus 2 smoke tests) at 97%+ coverage,
against real PostgreSQL and Redis. Ruff, Black, and MyPy (scoped to
`app/` + `main.py`) all clean. Live Docker e2e confirmed: all 5 workers
registered and leader-elected on startup; health/readiness real; the full
device-registration → login → push-token-registration → sync-enqueue →
autonomous-worker-completion lifecycle exercised end-to-end through real
HTTP against the running container; RBAC confirmed (403 non-admin, 401 no
token); database truncated and container removed after.
