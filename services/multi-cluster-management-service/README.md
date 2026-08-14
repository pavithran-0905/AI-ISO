# Multi-Cluster Management Service

Centralized cluster onboarding, lifecycle orchestration, fleet grouping,
credential validation, health monitoring, capacity analysis, upgrade
planning, policy propagation, compliance assessment, and workload
placement across hybrid, edge, and multi-cloud Kubernetes-conformant
clusters.

Implements `docs/066_Enterprise_Multi-Cluster_Management_Service.md`.

- **Port** 8037 · **Database** `aiios_multi_cluster` · **Redis db** 39

This service is a fleet control plane, not a Kubernetes distribution or
a GitOps/service-mesh runtime — see *Scope boundary* below for exactly
where it stops.

---

## The ideas that shape everything here

**A cluster only moves between adjacent, explicitly allowed lifecycle
states.** Skipping straight from `DISCOVERED` to `ACTIVE` would treat a
cluster this service has never validated or provisioned as fully
operational. Every hop in the state machine (`app/lifecycle/engine.py`)
exists because something real has to happen at that step.

**No component health reading is `HEALTHY` by default.** A cluster
nothing has checked yet is `UNKNOWN`, not healthy — an absence of
evidence is not evidence of health, and defaulting it to healthy is
exactly the failure mode that lets a genuinely down cluster sit
unnoticed.

**A cluster nobody has scanned against a compliance framework is
`NOT_ASSESSED`, never `COMPLIANT`.** Silence is not evidence of
compliance.

**Automatic failover-style gating principles apply here too: a
retention-lock-shaped guarantee protects lifecycle transitions.** A
`DELETE /clusters/{id}` call is not "always succeeds" — a cluster that
cannot validly reach `DECOMMISSIONING` from its current state is refused
with a `409 Conflict` naming exactly why, never silently coerced or left
to 500.

**Version skew is compared by catalog rank, never parsed semver.**
Version string formats differ enough across distributions (`v1.29.4` vs
`1.29.4-eks-1` vs a vendor build tag) that a shared parser would be a
second place to get distribution quirks wrong; each catalog entry
(`ClusterVersion.skew_rank`) carries a single ordinal this service
assigns itself, so comparing ranks is exact by construction.

**Enum-typed columns are plain `String`, not a SQL `Enum` type — every
comparison against a possibly-ORM-sourced value uses `==`, never `is`.**
A row found live in a session's identity map keeps its enum attribute as
the genuine Python enum instance; a row freshly materialized by a plain
`SELECT` gets back a raw `str` for that same column. Comparing the two
with `is` silently returns `False` for what is logically an equal value,
and — because *whether* an object is still identity-mapped depends on
Python-level memory management timing (a garbage-collected weak
reference), not on data correctness — this is a real, exploitable
production bug class, not a test-only quirk. Confirmed twice in this
build (see the `AI_MEMORY.md` entry) and fixed everywhere it appeared.

---

## What it does

### Cluster registration & lifecycle (`app/lifecycle/`, `app/registration/`, `app/services/fleet.py`)

Discovery → registration → validation → provisioning → configuration →
active, with upgrade/scaling/maintenance/suspend as reversible detours
from `ACTIVE` and decommission → archive as the one-way exit. Credential
validation (`app/registration/engine.py`) checks only what this
service's own row can know — a non-empty reference and a not-yet-expired
date — never the secret itself, which is secrets-management-service's
job (`ClusterCredential.credential_ref` is a lookup key, exactly the
posture `services/backup-dr-service` takes with `BackupTarget
.connection_ref`).

### Fleet grouping (`app/models/fleet.py`)

Cluster groups and regions a policy or report can target as a unit
instead of one cluster at a time.

### Health monitoring (`app/health/`)

Per-component readings (API server, etcd, control plane, worker nodes,
pod health) rolled up into one overall verdict against two independent
thresholds (degraded, unhealthy). A cluster whose `last_seen_at` has gone
stale is reported `OFFLINE` regardless of its last self-reported status —
a cluster that stopped phoning home is not still whatever it last said.

### Capacity management (`app/capacity/`)

Utilization, severity classification (ok/warning/critical against two
independent thresholds), and period-over-period growth rate — every rate
`None` on a zero denominator, never `0.0` or `1.0`.

### Upgrade management (`app/upgrades/`)

Version-skew validation against the catalog (refuses a downgrade, a
no-op, or a jump exceeding the configured maximum skew) and a rollback
recommendation triggered only by an *explicit* post-validation failure —
never by validation simply never having run.

### Policy management (`app/policies/`)

A policy targets a specific cluster or an entire group (never neither);
group targets are resolved by the caller from current membership, since
the pure engine has no database access and membership can change between
calls. Drift detection compares a desired-state hash against a live-state
hash and is explicit that "never observed" is not the same fact as
"observed, and it no longer matches."

### Compliance (`app/compliance/`)

Score-to-status classification (compliant / partially compliant /
non-compliant / not-assessed) against two independent thresholds, with a
remediation deadline computed from a configurable grace period and
reassessment scheduling that treats "never assessed" as always due.

### GitOps sync classification (`app/gitops/`)

A pure `desired-hash` vs `live-hash` comparison, reported `SYNCING`
during an in-progress sync regardless of what the hashes currently say.
No ArgoCD/FluxCD integration is wired in this build — see *Scope
boundary*.

### Workload placement (`app/placement/`)

Affinity/anti-affinity evaluation with no partial credit: every required
label must match and no forbidden label may be present with its
forbidden value. A placement that finds no eligible cluster is still
recorded (`FAILED`, no cluster reference) rather than silently dropped.

### Federation (`app/federation/`)

Cross-cluster distribution planning: a resource is never planned to
distribute to its own source, and duplicate targets collapse to one.
Planning is a pure computation recorded on the audit trail; there is no
live cross-cluster channel in this build — see *Scope boundary*.

### Analytics (`app/analytics/`)

Fleet-wide success/compliance/availability rates, every one `None` on a
zero denominator.

---

## Scope boundary

Per docs/066's own "DO NOT IMPLEMENT" section, this service does **not**
run a Kubernetes distribution, a container runtime, or a cloud vendor's
managed control plane. Consistent with that boundary, several spec
sections are implemented as real, tested decision logic with **no live
external-system client wired up**, matching the "declared seam" pattern
`services/backup-dr-service` established for MinIO/target-specific I/O:

- **GitOps** (`app/gitops/engine.py`): sync classification is real and
  tested; there is no ArgoCD/FluxCD API client.
- **Service mesh**: no Istio/Linkerd/Consul Connect integration; tracked
  only as a scope placeholder (`ServiceMeshType` enum).
- **Federation** (`app/federation/engine.py`): distribution *planning* is
  real; there is no live cross-cluster secret/config channel that
  executes the plan.
- **Cordon/drain** (`POST /clusters/{id}/cordon`, `.../drain`): these
  toggle this service's own `is_schedulable` flag and mark tracked
  workload placements `REBALANCING` — they do not call a live cluster's
  API server, since this build holds no cluster credentials capable of
  doing so.

---

## REST API

15 routes under `/clusters`, plus `/health`, `/liveness`, `/readiness`,
`/metrics` (Prometheus), `/docs` (OpenAPI). Every route derives its
tenant from the caller's JWT (`organization_id` claim) — never from a
query or body parameter. **The five fleet-wide `GET` routes
(`/clusters/health`, `/capacity`, `/compliance`, `/statistics`,
`/reports`) are registered ahead of `/clusters/{cluster_id}`** — FastAPI
matches routes in registration order, and reversing this would make
`GET /clusters/health` parse as a request for the cluster literally named
`"health"`.

| Method | Path                         | Purpose                                                |
| ------ | ---------------------------- | ------------------------------------------------------- |
| GET    | `/clusters/health`           | Fleet-wide health snapshot                               |
| GET    | `/clusters/capacity`         | Fleet-wide capacity readings for one resource kind        |
| GET    | `/clusters/compliance`       | Fleet-wide compliance assessments for one framework        |
| GET    | `/clusters/statistics`       | Rolled-up fleet statistics                                |
| GET    | `/clusters/reports`          | Generated reports, newest first                            |
| GET    | `/clusters`                  | List clusters                                              |
| POST   | `/clusters`                  | Register a cluster (administrator role required)            |
| GET    | `/clusters/{id}`             | Get one cluster                                             |
| PUT    | `/clusters/{id}`             | Update a cluster (administrator role required)               |
| DELETE | `/clusters/{id}`             | Start decommissioning (administrator role required; `409` if the current lifecycle state cannot reach `DECOMMISSIONING`) |
| POST   | `/clusters/{id}/validate`    | Revalidate a cluster's registered credential                 |
| POST   | `/clusters/{id}/upgrade`     | Plan an upgrade (administrator role required)                 |
| POST   | `/clusters/{id}/drain`       | Mark placed workloads for rebalancing (administrator role required) |
| POST   | `/clusters/{id}/cordon`      | Stop new workload placement (administrator role required)     |
| POST   | `/clusters/{id}/uncordon`    | Resume workload placement (administrator role required)        |

## Background workers

Five jobs, all **leader-elected** through `shared_core.scheduler` — each
is pure database work with no per-replica state:

| Worker              | Default interval | What it does                                                        |
| -------------------- | ----------------- | ---------------------------------------------------------------------- |
| Health sweep            | 60s            | Recomputes overall health from readings; marks stale clusters `OFFLINE` |
| Compliance sweep           | 3600s        | Notifies for every assessment past its remediation deadline             |
| Policy reconcile              | 1800s     | Times out stuck `PENDING` propagations; refreshes applied policies' due dates |
| Capacity analysis                | 300s    | Classifies every cluster's latest reading; warns on high utilization    |
| Statistics rollup                   | 900s | Idempotent per-window fleet statistics rollup                            |

## Configuration

Every fleet threshold is a configuration field
(`app/config/settings.py`), never a compiled-in constant.

Key environment variables (prefix
`AIIOS_MULTI_CLUSTER_MANAGEMENT_SERVICE_` for service-specific fields;
shared infrastructure fields use the platform-wide `AIIOS_DATABASE_*` /
`AIIOS_REDIS_*` / `AIIOS_RABBITMQ_*` prefixes):

- `PORT` (default `8037`), `JWT_PUBLIC_KEY_PATH`
- `STALE_CLUSTER_THRESHOLD_MINUTES`, `HEALTH_DEGRADED_COMPONENT_THRESHOLD`, `HEALTH_UNHEALTHY_COMPONENT_THRESHOLD`
- `CAPACITY_WARNING_UTILIZATION_FRACTION`, `CAPACITY_CRITICAL_UTILIZATION_FRACTION`
- `MAX_SUPPORTED_VERSION_SKEW`, `UPGRADE_DEFAULT_STRATEGY`
- `POLICY_PROPAGATION_TIMEOUT_SECONDS`, `POLICY_DRIFT_CHECK_INTERVAL_SECONDS`
- `COMPLIANCE_REASSESSMENT_DAYS`, `COMPLIANCE_REMEDIATION_GRACE_DAYS`
- `WORKERS_ENABLED` plus a `*_SECONDS` interval per worker

## Running locally

```bash
cd services/multi-cluster-management-service
uv sync
uv run alembic upgrade head
uv run uvicorn main:app --host 0.0.0.0 --port 8037
```

Requires PostgreSQL (database `aiios_multi_cluster`), Redis, and
RabbitMQ reachable per the `AIIOS_*` environment variables. **Every
AI-IOS service shares one Postgres instance but owns its own database and
its own Alembic version table**
(`alembic_version_multi_cluster_management_service`).

## Testing

```bash
uv run python -m pytest tests/ --cov=app --cov-report=term-missing
```

230 tests, 95.9% coverage. Every test that touches persistence runs
against a **real** PostgreSQL and Redis. Each test gets its own
SAVEPOINT-isolated database transaction (rolled back at teardown) and its
own tenant (`organization_id`).

Background workers are tested by calling `tick()` directly against a
real session factory bound to the test's own connection, using real
wall-clock time throughout. Cross-session assertions call
`await db_session.refresh(entity)` before asserting — see *the ideas that
shape everything here* above for why a plain re-`SELECT` cannot be
trusted to refresh an already-loaded object's enum-typed attributes on
its own.

Quality gates: `ruff check .`, `black --check .`, and
`mypy app/ main.py` (matching this project's CI convention of gating
`app/` and `main.py`, not `tests/`).
