# Backup & Disaster Recovery Service

Backup orchestration, snapshot management, restore and point-in-time
recovery, replication health monitoring, disaster recovery planning and
drills, automated/manual failover, immutability (retention locks and
legal holds), and RPO/RTO compliance reporting for every AI-IOS service
and infrastructure component.

Implements `docs/065_Enterprise_Backup_Disaster_Recovery_Service.md`.

- **Port** 8036 · **Database** `aiios_backup_dr` · **Redis db** 38

This is the one service on the platform whose own audit trail is itself
a disaster-recovery asset — it is append-only by construction, not just
by convention.

---

## The ideas that shape everything here

**A missing measurement and a passing one are different answers.** An
RPO/RTO target nobody has ever drilled against is `NOT_MEASURED`, never
assumed `MET` — reporting a plan as compliant because nothing has
contradicted it yet is exactly the gap this service exists to close
before a real incident finds it first.

**Immutability and legal hold are checked before age, every time,
unconditionally.** A retention sweep that computed "this archive is past
its retention period" and only then asked about a legal hold would be
one refactor away from getting the order backwards; every planning
function here takes the lock state as a required parameter so there is
no path that can forget to ask. A legal hold outranks an expired
retention lock unconditionally — an expired lock underneath a hold does
not mean "fine to delete."

**A retention lock may only be extended, never shortened.** The entire
point of a WORM guarantee is that the actor who could otherwise delete
the archive outright cannot undo the lock by re-applying a shorter one.

**An incremental backup's restorability depends on every link back to
its last full backup, not just its own status.** Chain validation walks
`parent_job_id` all the way to a `FULL`/`SNAPSHOT`/`CONTINUOUS` root,
checking every link is `COMPLETED` or `VERIFIED` — a chain with one
failed link in the middle is not "mostly restorable," it cannot be
restored past the break, and this is checked before a restore ever needs
it, not discovered during one.

**A restore point is chosen, never rounded forward.** Given a requested
instant, the engine finds the latest point at or before it and says so
explicitly. Rounding forward to "the closest one" would silently restore
data from *after* the moment someone is trying to recover from — usually
the instant right before whatever went wrong.

**Automatic failover requires unanimous, non-empty health evidence.
Manual and failback do not.** An empty health-check result set is not
evidence of health, it is an absence of evidence, and automation may
never act on it. A human invoking a manual failover has context
(a known-flaky check, an ongoing incident call) this engine cannot see,
and is allowed to proceed against evidence that looks bad — the
alternative is silently downgrading every manual override into an
automatic-shaped decision, which removes the one thing a manual override
is for.

**Recovery order is a topological sort, never the declared list order.**
A plan authored with the database group listed after the API group but
declared as its *dependency* still recovers the database first. Treating
declaration order as the answer is how a real recovery brings a service
up pointed at a database that is not there yet.

---

## What it does

### Backup orchestration (`app/backup/`, `app/services/backup.py`)

Nineteen target kinds (PostgreSQL, Neo4j, Redis, RabbitMQ, MinIO,
Kubernetes resources, and more) share one job lifecycle: start → complete
(chain-validated, deduplicated by checksum+size) → fail. A job whose
chain fails validation is marked `FAILED`, never `COMPLETED` with a
note — a restore planner trusts `COMPLETED` to mean the chain is
walkable. Schedules catch up a missed run to "now plus one interval"
rather than firing a backlog of missed runs back to back the moment a
worker comes back online.

### Snapshots (`app/snapshots/`)

Point-in-time storage-layer snapshots, distinct from a job's streamed
archive. Expiration is recomputed from `expires_at` every time it
matters, never trusted from a stale flag. Per-target quotas evict
oldest-first — the newest snapshots are what a caller is most likely to
restore from.

### Restore & point-in-time recovery (`app/restore/`)

Restore-point selection never rounds forward (see above). Every restore
— including a preview — is persisted as a real, auditable `RestoreJob`
row, not a throwaway computation. Preview builders flag an in-place
restore as destructive exactly when the target is the original target,
never for a restore into a scratch environment.

### Replication monitoring (`app/replication/`)

Lag is classified against two independent thresholds (warning, critical)
into `IN_SYNC` / `LAGGING` / `STALLED` / `SYNCING`. `None` lag (nothing
has synced yet) is always `SYNCING`, never defaulted to healthy or
lagging — both would be a claim about a rate that was never measured.

### Retention & immutability (`app/retention/`, `app/immutability/`)

Tiering (hot → archive) and deletion planning, with legal hold and
retention locks as an absolute veto checked first and unconditionally
(see above). A policy whose `archive_after_days` is not strictly before
its `retention_days` is rejected outright — such a policy has no tier
transition to make.

### Verification (`app/verification/`)

A checksum match is the only thing that produces a `PASSED` verdict — a
missing expected checksum or an unrecognised algorithm is a refusal to
judge (`SKIPPED`), never a pass by default. Periodic sampling always
includes every overdue archive regardless of the sample fraction; the
fraction only spreads load across archives merely due for their *next*
routine check.

### Disaster recovery planning & drills (`app/dr_plans/`)

Recovery-group sequencing is a topological sort with alphabetical
tie-breaking (see above), refusing on a detected cycle or an unknown
dependency rather than guessing. RPO/RTO compliance is always one of
`MET` / `VIOLATED` / `NOT_MEASURED` — never assumed met for an untested
plan.

### Failover (`app/failover/`)

Health-check aggregation and the automatic/manual authorization gate
(see above). `authorize_failover()` is the single choke point every
failover path — API route and future automation alike — must pass
through.

### Encryption & analytics (`app/encryption/`, `app/analytics/`)

Key rotation is due-date arithmetic only; the actual AES-256-GCM sealing
lives in the storage layer this service calls out to. Every rate
(success rate, compliance rate, storage growth rate) is `None` on a zero
denominator, never `0.0` or `1.0` — a rate invented from no evidence is
worse than an honestly missing one.

---

## REST API

12 routes under `/backup`, plus `/health`, `/liveness`, `/readiness`,
`/metrics` (Prometheus), `/docs` (OpenAPI). Every route derives its
tenant from the caller's JWT (`organization_id` claim) — never from a
query or body parameter, since a repository scopes on whatever value it
is handed, and a caller supplying somebody else's organization id would
be served their backups or, worse, able to request a restore into them.

| Method | Path                    | Purpose                                                |
| ------ | ----------------------- | ------------------------------------------------------- |
| GET    | `/backup/jobs`          | List recent backup jobs                                 |
| POST   | `/backup/jobs`          | Start a backup job (administrator role required)         |
| GET    | `/backup/schedules`     | List enabled backup schedules                            |
| POST   | `/backup/schedules`     | Create a schedule (administrator role required)           |
| GET    | `/backup/snapshots`     | List recent snapshots                                    |
| POST   | `/backup/restore`       | Select a restore point and preview or run a restore       |
| POST   | `/backup/failover`      | Initiate a failover (administrator role required)         |
| POST   | `/backup/failback`      | Fail back to the original site (administrator role required) |
| GET    | `/backup/dr-plans`      | List active DR plans                                      |
| POST   | `/backup/dr-tests`      | Record a DR test/drill result (administrator role required) |
| GET    | `/backup/statistics`    | Rolled-up backup/restore/replication/compliance statistics |
| GET    | `/backup/reports`       | Generated reports, newest first                            |

## Background workers

Five jobs, all **leader-elected** through `shared_core.scheduler` — each
is pure database (and, for the backup scheduler, orchestration) work
with no per-replica state, so N replicas would be N times the load for
an identical result:

| Worker               | Default interval | What it does                                                     |
| --------------------- | ----------------- | ------------------------------------------------------------------ |
| Backup scheduler        | 60s             | Starts every due schedule's job, advances `next_run_at`             |
| Retention sweep           | 3600s          | Applies every enabled policy's tiering and deletion plan             |
| Verification sweep          | 3600s        | Queues checksum verification for jobs due their next check          |
| Replication monitor            | 120s       | Reclassifies every replication job's status from its recorded lag   |
| Statistics rollup                 | 900s     | Idempotent per-window backup/restore/DR-test rollup                 |

The verification sweep and replication monitor both declare an
intentional seam rather than faking I/O: actually re-reading archive
bytes or measuring live replication lag is target-specific work this
build does not wire a client for. Queuing the check (verification) and
reclassifying from the last-recorded reading (replication) is the whole
job; performing the read is not.

## Configuration

Every backup/restore/replication/failover/retention/verification/DR
threshold is a configuration field (`app/config/settings.py`), never a
compiled-in constant — an RPO/RTO target, a bandwidth cap, or a retention
lock duration baked into the code is one a deployment cannot tune to its
actual continuity requirements without a release.

Key environment variables (prefix `AIIOS_BACKUP_DR_SERVICE_` for
service-specific fields; shared infrastructure fields use the
platform-wide `AIIOS_DATABASE_*` / `AIIOS_REDIS_*` / `AIIOS_RABBITMQ_*`
prefixes):

- `PORT` (default `8036`), `JWT_PUBLIC_KEY_PATH`
- `DEFAULT_FULL_INTERVAL_DAYS`, `MAX_CONCURRENT_BACKUP_JOBS`, `CHECKSUM_ALGORITHM`
- `SNAPSHOT_DEFAULT_EXPIRY_DAYS`, `MAX_SNAPSHOTS_PER_TARGET`
- `PITR_MAX_LOOKBACK_DAYS`
- `REPLICATION_LAG_WARNING_SECONDS`, `REPLICATION_LAG_CRITICAL_SECONDS`
- `DEFAULT_RPO_MINUTES`, `DEFAULT_RTO_MINUTES`
- `DEFAULT_RETENTION_LOCK_DAYS`, `KEY_ROTATION_DAYS`
- `VERIFICATION_SAMPLE_RESTORE_FRACTION`, `VERIFICATION_MAX_AGE_DAYS`
- `WORKERS_ENABLED` plus a `*_SECONDS` interval per worker

## Running locally

```bash
cd services/backup-dr-service
uv sync
uv run alembic upgrade head
uv run uvicorn main:app --host 0.0.0.0 --port 8036
```

Requires PostgreSQL (database `aiios_backup_dr`), Redis, and RabbitMQ
reachable per the `AIIOS_*` environment variables. **Every AI-IOS service
shares one Postgres instance but owns its own database and its own
Alembic version table** (`alembic_version_backup_dr_service`) — the
default single `alembic_version` table cannot track more than one
service's migration chain at a time, since every service connects to the
same physical database.

## Testing

```bash
uv run python -m pytest tests/ --cov=app --cov-report=term-missing
```

317 tests, 97.6% coverage. Every test that touches persistence runs
against a **real** PostgreSQL and Redis — nothing here mocks
infrastructure. Each test gets its own SAVEPOINT-isolated database
transaction (rolled back at teardown) and its own tenant
(`organization_id`), so every test is incidentally also a
tenant-isolation test.

Background workers are tested by calling `tick()` directly against a
real session factory bound to the test's own connection, using real
wall-clock time throughout (matching every worker's own internal
`datetime.now(UTC)`) — a fixed historical constant would fall outside a
worker's real query window and produce a test that passes without the
loop body ever executing. Cross-session assertions (checking that a
worker's own, separate session actually mutated a row) call
`await db_session.refresh(entity)` before asserting, since SQLAlchemy's
identity map does not implicitly refresh an already-loaded object from a
plain re-`SELECT` on a different session sharing the same connection.

Quality gates: `ruff check .`, `black --check .`, and
`mypy app/ main.py` (matching this project's CI convention of gating
`app/` and `main.py`, not `tests/`).
