# Cloud Management Service

Multi-cloud account/resource discovery, provisioning, network/storage/
compute/database/Kubernetes management, IAM tracking, governance,
Infrastructure-as-Code deployment tracking, FinOps, capacity planning,
service catalog, and compliance across hybrid and multi-cloud
infrastructure.

Implements `docs/068_Enterprise_Cloud_Management_Service.md`.

- **Port** 8039 · **Database** `aiios_cloud` · **Redis db** 41

This service is a cloud fleet control plane, not a cloud provider, a
hypervisor, or a billing engine — see *Scope boundary* below for
exactly where it stops.

---

## The ideas that shape everything here

**A resource only moves between adjacent, explicitly allowed lifecycle
states.** Skipping straight from `DISCOVERED` to `ACTIVE` would treat a
resource this service has never provisioned or imported as fully
operational. Every hop in the state machine (`app/resources/engine.py`)
exists because something real has to happen at that step.

**A `DELETE /cloud/resources/{id}` call is not "always succeeds."** A
resource that cannot validly reach `DELETING` from its current
lifecycle state is refused with a `409 Conflict` naming exactly why,
never silently coerced or left to crash as an unhandled 500.

**No utilization reading at all is never treated as "idle."** A
resource nothing has measured yet has not been proven idle — it has
simply not been looked at, the same discipline this platform's health
engines apply everywhere: absence of evidence is not evidence.

**A domain field must never reuse one of `BaseEntityMixin`'s reserved
column names** (`id`, `created_at`, `updated_at`, `is_active`,
`organization_id`, `project_id`, `version`). This service's own
`CloudResource` needed a foreign key to a provider-side project (a GCP
project, an Azure resource group) — named `cloud_project_id`, never
`project_id`, since `project_id` is already reserved as AI-IOS's own
internal project-scoping column, a wholly different concept. Checked
proactively from the first draft, learned the hard way by
`services/edge-management-service` in Prompt 067 (see its own README
and `AI_MEMORY.md` for the `is_active` collision that lesson came
from).

**Enum-typed columns are plain `String`, not a SQL `Enum` type — every
comparison against a possibly-ORM-sourced value uses `==`, never `is`.**
Applied proactively in every engine from the first draft, per
`services/multi-cluster-management-service`'s own hard-won lesson.

**Cost recorded, budgets tracked, drift classified -- never a live
cloud billing/metrics/provider API behind any of it.** See *Scope
boundary*.

---

## What it does

### Cloud accounts (`app/accounts/`, `app/services/accounts.py`, `app/services/providers.py`)

Provider registration, per-account enrollment credential validation
(checks only what this service's own row can know -- a non-empty
reference and a not-yet-expired date -- never the secret itself, which
is secrets-management-service's job), region catalog, and provider-side
project grouping (a GCP project, an Azure resource group, an AWS
organizational unit).

### Resource discovery & lifecycle (`app/resources/`, `app/services/resources.py`)

Discovery → provisioning/import → active, with update/scale/suspend/
stop as reversible detours from `ACTIVE` and delete → archive as the
one-way exit. Per-category detail records (`app/services/resource_details.py`)
attach compute, storage, network, database, or managed-Kubernetes
attributes to a base resource row -- `CloudKubernetes.cluster_reference_id`
is a cross-service reference to `services/multi-cluster-management-service`'s
own `Cluster.id` (Prompt 066 integration), never a foreign key, since
that table lives in a different service's database entirely.

### Governance (`app/governance/`)

Tag, naming, and quota policy evaluation -- every evaluation names
every violation it found, never just a pass/fail bit.

### FinOps (`app/finops/`)

Budget threshold classification (ok/warning/critical/exceeded), linear
spend forecasting, idle-resource detection, and rightsizing
recommendations, all driven by a `utilization_fraction` reading
monitoring integration (Prompt 044) supplies -- this service classifies
it, never measures it itself.

### Capacity planning (`app/capacity/`)

Growth-rate computation and linear forecasting, with a scaling
recommendation from the latest utilization reading -- `None` on a
zero-or-negative period, never a nonsensical rate.

### Drift (`app/drift/`)

A pure `desired-hash` vs `live-hash` comparison with severity
classification by how many fields disagree, mirroring
`services/multi-cluster-management-service`'s own GitOps sync
discipline and `services/edge-management-service`'s digital twin sync
discipline.

### Infrastructure as Code (`app/iac/`)

Deployment state tracking (Terraform/OpenTofu/Pulumi/CloudFormation
import/ARM import) through an explicit transition table -- a plan that
never applied cannot be "drifted."

### Service catalog (`app/catalog/`)

An approval workflow a template must pass through before it is
self-service-provisionable -- draft → pending approval → approved (or
rejected, revisable back to draft) → deprecated.

### Compliance (`app/compliance/`)

Score-to-status classification (compliant / partially compliant /
non-compliant / not-assessed) against two independent thresholds, with
a remediation deadline computed from a configurable grace period.

### Analytics (`app/analytics/`)

Fleet-wide success/compliance rates, every one `None` on a zero
denominator.

---

## Scope boundary

Per docs/068's own "DO NOT IMPLEMENT" section, this service does **not**
call any cloud provider's API, run a hypervisor, or compute real
billing. Consistent with that boundary, several spec sections are
implemented as real, tested decision logic with **no live external
system wired up**, matching the "declared seam" pattern
`services/backup-dr-service` established in Prompt 065 and every
service since:

- **FinOps** (`app/finops/engine.py`): budget/idle/rightsizing
  classification is real and tested; there is no live cloud cost/usage
  API. `CloudCompute.utilization_fraction` is a reading supplied by
  monitoring integration (Prompt 044), classified here, never measured.
- **Resource discovery**: `POST /cloud/resources/discover` records a
  resource this service was told about; there is no live provider SDK
  crawling actual cloud accounts.
- **Drift**: `app/drift/engine.py`'s hash comparison is real; there is
  no live provider API polling actual resource state to compute the
  live-state hash.
- **IaC**: `app/iac/engine.py`'s deployment state tracking is real;
  there is no live Terraform/OpenTofu/Pulumi execution engine.
- **IAM**: roles/policies/groups/users/federation/OIDC/SAML/service
  accounts are governed through `app/governance/` policy evaluation;
  there is no live identity provider federation.

---

## REST API

15 routes under `/cloud`, plus `/health`, `/liveness`, `/readiness`,
`/metrics` (Prometheus), `/docs` (OpenAPI). Every route derives its
tenant from the caller's JWT (`organization_id` claim) — never from a
query or body parameter. `GET /cloud/providers` lists this
organization's registered provider integrations; there is no
`POST /cloud/providers` per docs/068's own route list -- providers are
onboarded through this service's own administrative tooling, not a
tenant-facing endpoint.

| Method | Path                          | Purpose                                                              |
| ------ | ------------------------------ | ------------------------------------------------------------------- |
| GET    | `/cloud/providers`             | List registered cloud provider integrations                          |
| GET    | `/cloud/accounts`              | List accounts                                                        |
| POST   | `/cloud/accounts`               | Register an account (administrator role required; `409` on an unusable enrollment credential) |
| GET    | `/cloud/resources`               | List resources                                                       |
| POST   | `/cloud/resources/discover`        | Discover a resource (administrator role required)                    |
| POST   | `/cloud/resources/provision`         | Advance a resource's lifecycle (administrator role required; `409` if refused) |
| PUT    | `/cloud/resources/{id}`                | Update a resource (administrator role required)                       |
| DELETE | `/cloud/resources/{id}`                  | Start deleting (administrator role required; `409` if the current lifecycle state cannot reach `DELETING`) |
| GET    | `/cloud/cost`                              | Cost line items for an account                                        |
| GET    | `/cloud/budgets`                             | List budgets                                                          |
| POST   | `/cloud/budgets`                               | Create a budget (administrator role required)                          |
| GET    | `/cloud/optimization`                            | Idle-resource / rightsizing recommendations                            |
| GET    | `/cloud/compliance`                                | Compliance assessments                                                 |
| GET    | `/cloud/statistics`                                  | Rolled-up fleet statistics                                              |
| GET    | `/cloud/reports`                                       | Generated reports, newest first                                          |

## Background workers

Five jobs, all **leader-elected** through `shared_core.scheduler` — each
is pure database work with no per-replica state:

| Worker                     | Default interval | What it does                                                              |
| --------------------------- | ----------------- | ---------------------------------------------------------------------------- |
| Account health sweep            | 300s          | Reclassifies every account's health from revalidation staleness              |
| Drift sweep                        | 900s      | Escalates stale unresolved drift events one severity level and re-notifies    |
| Budget sweep                           | 900s  | Recomputes every budget's spend from recorded costs; publishes on crossing     |
| Compliance sweep                          | 3600s | Notifies for every assessment past its remediation deadline                     |
| Statistics rollup                            | 900s | Idempotent per-window fleet statistics rollup                                    |

## Configuration

Every fleet threshold is a configuration field
(`app/config/settings.py`), never a compiled-in constant.

Key environment variables (prefix `AIIOS_CLOUD_MANAGEMENT_SERVICE_` for
service-specific fields; shared infrastructure fields use the
platform-wide `AIIOS_DATABASE_*` / `AIIOS_REDIS_*` / `AIIOS_RABBITMQ_*`
prefixes):

- `PORT` (default `8039`), `JWT_PUBLIC_KEY_PATH`
- `STALE_ACCOUNT_THRESHOLD_MINUTES`, `STALE_RESOURCE_THRESHOLD_MINUTES`
- `BUDGET_WARNING_UTILIZATION_FRACTION`, `BUDGET_CRITICAL_UTILIZATION_FRACTION`, `IDLE_RESOURCE_THRESHOLD_DAYS`
- `COMPLIANCE_REASSESSMENT_DAYS`, `COMPLIANCE_REMEDIATION_GRACE_DAYS`
- `DRIFT_SWEEP_STALE_AFTER_MINUTES`
- `WORKERS_ENABLED` plus a `*_SECONDS` interval per worker

## Running locally

```bash
cd services/cloud-management-service
uv sync
uv run alembic upgrade head
uv run uvicorn main:app --host 0.0.0.0 --port 8039
```

Requires PostgreSQL (database `aiios_cloud`), Redis, and RabbitMQ
reachable per the `AIIOS_*` environment variables. **Every AI-IOS
service shares one Postgres instance but owns its own database and its
own Alembic version table** (`alembic_version_cloud_management_service`).

## Testing

```bash
uv run python -m pytest tests/ --cov=app --cov-report=term-missing
```

229 tests, 96.5% coverage. Every test that touches persistence runs
against a **real** PostgreSQL and Redis. Each test gets its own
SAVEPOINT-isolated database transaction (rolled back at teardown) and
its own tenant (`organization_id`).

Background workers are tested by calling `tick()` directly against a
real session factory bound to the test's own connection, using real
wall-clock time throughout. Live Docker e2e additionally confirmed all
five workers fire autonomously on their own schedule — never manually
triggered — by watching the container's own logs across several
intervals and observing real database writes.

Quality gates: `ruff check .`, `black --check .`, and
`mypy app/ main.py` (matching this project's CI convention of gating
`app/` and `main.py`, not `tests/`).
