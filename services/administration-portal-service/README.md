# Administration Portal Service

The centralized operational control plane for global platform
administration, multi-tenant management, feature flags, platform
configuration, diagnostics, background job management, API management,
security administration, maintenance, and platform health.

Implements `docs/070_Enterprise_Administration_Portal_Service.md`.

- **Port** 8041 · **Database** `aiios_admin` · **Redis db** 43

This service is the platform's own super-admin console, not an
identity provider, an operating system, a cloud provider console, or a
third-party monitoring system — see *Scope boundary* below for exactly
where it stops.

---

## The ideas that shape everything here

**A tenant, organization, maintenance window, or background job only
moves between adjacent, explicitly allowed states.** Skipping straight
from `PROVISIONING` to `SUSPENDED` would suspend a tenant that was
never actually activated; a `SCHEDULED` maintenance window jumping to
`COMPLETED` would skip the approval it never received. Every hop in
each of the four transition tables (`app/tenants/engine.py`,
`app/organizations/engine.py`, `app/maintenance/engine.py`,
`app/jobs/engine.py`) exists because something real has to happen at
that step.

**A domain field must never reuse one of `BaseEntityMixin`'s reserved
column names** (`id`, `created_at`, `updated_at`, `is_active`,
`organization_id`, `project_id`, `version`). Every "currently usable"
flag this service needed — `AdminSession.is_enabled`,
`PlatformAnnouncement.is_enabled` — is named `is_enabled`, deliberately
never `is_active`, since `is_active` is already `BaseEntityMixin`'s own
soft-delete flag that every repository's `_base_select()` filters on.
Checked proactively from the first model draft, learned the hard way by
`services/edge-management-service` in Prompt 067.

**Enum-typed columns are plain `String`, not a SQL `Enum` type — every
comparison against a possibly-ORM-sourced value uses `==`, never `is`.**
Applied proactively in every engine from the first draft, per
`services/multi-cluster-management-service`'s own hard-won lesson.

**A feature flag's kill switch always wins, and rollout bucketing is
deterministic, not random.** `app/feature_flags/engine.py` checks
`is_killed` before anything else — no rollout percentage, schedule, or
version constraint can turn a killed flag back on — and buckets each
target with a stable SHA-256 hash of `flag_name:target_ref`, so the
same caller never flickers between on and off for the same flag between
requests.

**An overall health status is always the worst of its components, never
an average.** `app/diagnostics/engine.py` aggregates every component
reading to the single worst one — one unhealthy dependency makes the
platform unhealthy regardless of how many others are fine, and an empty
reading set is `UNKNOWN`, never a falsely reassuring `HEALTHY`.

**Every password-policy violation is named, never just a pass/fail
bit**, and an IP allowlist with zero entries means no restriction is
configured — not that nothing is allowed (`app/security/engine.py`).

---

## What it does

### Organizations & tenants (`app/organizations/`, `app/tenants/`, `app/services/organizations.py`, `app/services/tenants.py`)

Organization lifecycle (active ⇄ suspended → archived), tenant
provisioning through a real `TenantProvisioning` record, tenant
lifecycle (provisioning → active ⇄ suspended/migrating → deleting →
deleted), per-tenant settings/limits/usage/health readings, and
limit-vs-usage classification (ok/warning/exceeded) — publishing
`TenantCreated`/`TenantUpdated`/`TenantDeleted`.

### Platform settings & configuration (`app/services/settings.py`)

Global platform settings (simple key/value administrative state) and
system configuration entries, the latter publishing
`ConfigurationChanged` on every change — its own history lives on the
immutable `system_audit` trail rather than a second, separately
maintained history table.

### Feature flags (`app/feature_flags/`, `app/services/settings.py`)

Global/tenant/organization/project-scoped flags with a kill switch,
scheduled rollout windows, deterministic percentage-rollout bucketing,
flag dependencies (`depends_on_flag_id`), and min/max platform version
constraints — publishing `FeatureFlagUpdated`.

### Background jobs (`app/jobs/`, `app/services/jobs.py`)

Job lifecycle (queued → running → succeeded/failed/cancelled; failed →
retrying → running or dead-letter) with an append-only
`JobHistory` transition log and exponential-backoff retry eligibility.

### Maintenance (`app/maintenance/`, `app/services/maintenance.py`)

Scheduling with real overlap conflict detection against every other
non-terminal window, an approval workflow, and autonomous start/complete
transitions on the window's own schedule — notifying
`notify_maintenance_scheduled` and publishing
`MaintenanceStarted`/`MaintenanceCompleted`.

### Announcements (`app/services/announcements.py`)

Global/tenant-scoped banner messages with an enable/retract lifecycle.

### API management (`app/api_management/`, `app/services/api_keys.py`)

API key issuance/rotation/revocation with the raw key returned exactly
once at issuance (only its SHA-256 hash is ever persisted), expiry and
rotation-due detection, and idempotent per-window request-count usage
rollup.

### Security administration (`app/security/`, `app/services/security.py`)

Named-violation password policy validation, CIDR-based IP allowlist
matching, session-expiry checking, and security event recording —
notifying `notify_security_event` and publishing
`SecurityPolicyUpdated` on a policy change.

### Diagnostics & platform health (`app/diagnostics/`, `app/services/diagnostics.py`)

Latency-based health classification (healthy/degraded/unhealthy/unknown)
against configurable thresholds, idempotent per-component health-check
readings, and worst-of aggregation into one overall status — publishing
`PlatformHealthChanged` on every real crossing.

### Analytics, statistics & reports (`app/analytics/`, `app/services/statistics.py`, `app/services/reports.py`)

Success/availability rates that are `None` on a zero denominator rather
than a misleading `0%`/`100%`, idempotent per-window platform
statistics rollup, and tenant/platform/security/API/feature/health/
operational/audit report generation.

### Admin sessions & actions (`app/services/admin_sessions.py`)

Administrator session lifecycle (start, force logout, usability
check) publishing `AdminLogin`, and a separate operational log of
session-level administrative actions — distinct from the platform-wide
`system_audit` trail (see `app/models/admin.py`'s own docstring for
why the two are not conflated).

### Audit (`app/services/audit.py`)

The one write path onto the immutable `system_audit` trail — every
other service calls through here rather than constructing rows
directly, so administrative logins, configuration changes, feature flag
changes, tenant operations, security operations, API management, and
maintenance operations cannot quietly stop being recorded through a
second, slightly different construction path.

---

## Scope boundary

Per docs/070's own "DO NOT IMPLEMENT" section, this service does **not**
implement identity provider software, operating system administration,
cloud provider administration, or third-party monitoring systems.
Consistent with that boundary, several capabilities are implemented as
real, tested decision logic with **no live external system wired up**,
matching the "declared seam" pattern `services/backup-dr-service`
established in Prompt 065 and every service since:

- **License expiration notifications**
  (`app/services/notifications.py`): `notify_license_expiration` is a
  real, tested method, but nothing in this service's own workers or
  routes calls it — license data is `services/license-billing-service`'s
  own system of record (Prompt 069 integration), so the trigger for
  this notification has to come from that integration, not from any
  fact this service's own database holds.
- **Statistics rollup's `user_count`** (`app/workers/statistics_rollup.py`):
  a scoped proxy — the count of distinct administrators with a
  currently-enabled session, not an end-user count. This service holds
  no end-user table of its own; that is the identity/auth service's
  system of record (Prompt 030/032 integration).
- **Organizations/tenants**: `app/models/tenants.py`'s `Organization`
  and `Tenant` rows are this service's own administrative view,
  scoped like every other AI-IOS table by the calling organization's
  `organization_id` — not a live sync against
  `services/organization-service` (Prompt 033); `Organization.external_ref`
  is an unenforced correlation id, never a foreign key, since that
  table lives in a different service's database entirely.

---

## REST API

16 routes, plus `/health`, `/liveness`, `/readiness`, `/metrics`
(Prometheus), `/docs` (OpenAPI). Every route derives its tenant from
the caller's JWT (`organization_id` claim) — never from a query or body
parameter. Several capability areas above (API management, security
administration, maintenance, organizations, announcements) have no
route of their own beyond what docs/070's own REST APIs section lists —
exactly the same "real logic, spec-scoped routing" pattern
`services/cloud-management-service` established for provider
registration in Prompt 068.

| Method | Path                          | Purpose                                                              |
| ------ | ------------------------------ | ------------------------------------------------------------------- |
| GET    | `/admin/dashboard`             | Platform dashboard: tenant/job/maintenance counts and overall health |
| GET    | `/admin/settings`               | List platform settings                                                |
| PUT    | `/admin/settings`                 | Create or update one platform setting (administrator role required)    |
| GET    | `/admin/tenants`                    | List tenants                                                             |
| POST   | `/admin/tenants`                      | Provision a tenant (administrator role required)                          |
| PUT    | `/admin/tenants/{id}`                   | Advance a tenant's lifecycle (administrator role required; `409` if refused) |
| DELETE | `/admin/tenants/{id}`                     | Start deleting a tenant (administrator role required; `409` if refused)        |
| GET    | `/admin/feature-flags`                      | List feature flags                                                               |
| POST   | `/admin/feature-flags`                        | Create a feature flag (administrator role required)                               |
| PUT    | `/admin/feature-flags/{id}`                     | Update a feature flag (administrator role required)                                 |
| GET    | `/admin/jobs`                                     | List background jobs                                                                  |
| POST   | `/admin/jobs`                                       | Enqueue a background job (administrator role required)                                 |
| GET    | `/admin/diagnostics`                                  | Recent diagnostic runs                                                                   |
| GET    | `/admin/health`                                         | Platform health: overall status plus every component reading                              |
| GET    | `/admin/statistics`                                       | Rolled-up platform statistics                                                                |
| GET    | `/admin/reports`                                            | Generated reports, newest first                                                                |

## Background workers

Five jobs, all **leader-elected** through `shared_core.scheduler` — each
is pure database work with no per-replica state:

| Worker                     | Default interval | What it does                                                              |
| --------------------------- | ----------------- | ---------------------------------------------------------------------------- |
| Health sweep                     | 60s           | Checks real database/cache latency for every organization and records readings |
| Maintenance sweep                    | 300s      | Starts approved windows and completes in-progress windows on their own schedule |
| Job retry sweep                          | 60s   | Retries failed jobs past their backoff window; dead-letters exhausted ones      |
| API key expiry sweep                        | 3600s | Expires API keys past `expires_at`                                                |
| Statistics rollup                              | 900s | Idempotent per-window platform statistics rollup                                    |

## Configuration

Every administrative threshold is a configuration field
(`app/config/settings.py`), never a compiled-in constant.

Key environment variables (prefix `AIIOS_ADMINISTRATION_PORTAL_SERVICE_`
for service-specific fields; shared infrastructure fields use the
platform-wide `AIIOS_DATABASE_*` / `AIIOS_REDIS_*` / `AIIOS_RABBITMQ_*`
prefixes):

- `PORT` (default `8041`), `JWT_PUBLIC_KEY_PATH`
- `ADMIN_SESSION_MAX_AGE_MINUTES`
- `MAINTENANCE_REMINDER_HOURS_BEFORE`
- `JOB_DEFAULT_MAX_ATTEMPTS`, `JOB_RETRY_BACKOFF_SECONDS`
- `HEALTH_CHECK_STALE_MINUTES`
- `API_KEY_EXPIRY_REMINDER_DAYS_BEFORE`
- `STATISTICS_WARNING_AVAILABILITY_FRACTION`
- `WORKERS_ENABLED` plus a `*_SECONDS` interval per worker

## Running locally

```bash
cd services/administration-portal-service
uv sync
uv run alembic upgrade head
uv run uvicorn main:app --host 0.0.0.0 --port 8041
```

Requires PostgreSQL (database `aiios_admin`), Redis, and RabbitMQ
reachable per the `AIIOS_*` environment variables. **Every AI-IOS
service shares one Postgres instance but owns its own database and its
own Alembic version table** (`alembic_version_administration_portal_service`).

## Testing

```bash
uv run python -m pytest tests/ --cov=app --cov-report=term-missing
```

247 tests, 97.4% coverage. Every test that touches persistence runs
against a **real** PostgreSQL and Redis. Each test gets its own
SAVEPOINT-isolated database transaction (rolled back at teardown) and
its own tenant (`organization_id`). The health sweep worker's own tests
run against a real Postgres engine and a real Redis client, not mocks.

Background workers are tested by calling `tick()` directly against a
real session factory bound to the test's own connection, using real
wall-clock time throughout. Live Docker e2e additionally confirmed all
five workers register and acquire scheduler leadership on startup, and
both the health sweep and statistics rollup workers fire autonomously
on their own schedule — never manually triggered — writing real
`health_checks` and `system_statistics` rows observed directly in the
database.

Quality gates: `ruff check .`, `black --check .`, and
`mypy app/ main.py` (matching this project's CI convention of gating
`app/` and `main.py`, not `tests/`).
