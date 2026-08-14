# Edge Management Service

Site/device onboarding, zero-touch provisioning, device lifecycle,
health monitoring, offline-first store-and-forward synchronization,
OTA/firmware updates, edge AI model deployment, industrial protocol
connectivity tracking, digital twin sync, and remote access across a
distributed edge/industrial fleet.

Implements `docs/067_Enterprise_Edge_Management_Service.md`.

- **Port** 8038 · **Database** `aiios_edge` · **Redis db** 40

This service is a fleet control plane for edge devices, not a PLC
runtime, an industrial protocol stack, or a real-time operating system —
see *Scope boundary* below for exactly where it stops.

---

## The ideas that shape everything here

**A device only moves between adjacent, explicitly allowed lifecycle
states.** Skipping straight from `DISCOVERED` to `ACTIVE` would treat a
device this service has never provisioned or configured as fully
operational. Every hop in the state machine (`app/devices/engine.py`)
exists because something real has to happen at that step.

**No component health reading is `HEALTHY` by default.** A device
nothing has checked yet is `UNKNOWN`, not healthy — an absence of
evidence is not evidence of health.

**A protocol endpoint nothing has checked recently is `UNKNOWN`, never
`CONNECTED`.** Connectivity this service has not verified recently is
not evidence either way — see `app/protocols/engine.py`.

**A `DELETE /edge/devices/{id}` call is not "always succeeds."** A
device that cannot validly reach `RETIRING` from its current lifecycle
state is refused with a `409 Conflict` naming exactly why, never
silently coerced or left to crash as an unhandled 500.

**Firmware/OTA version skew is compared by catalog rank, never parsed
semver.** Version string formats differ enough across device types (a
PLC's firmware numbering has nothing to do with a Raspberry Pi's OS
image tag) that a shared parser would be a second place to get
device-type quirks wrong; each catalog entry (`EdgeFirmware.skew_rank`)
carries a single ordinal this service assigns itself.

**A configuration rollback selects an earlier row; it never
reconstructs one.** Every applied configuration value is its own
immutable row, so "roll back" means "reactivate an existing,
already-applied revision" — never regenerating a value that could
regenerate incorrectly.

**Enum-typed columns are plain `String`, not a SQL `Enum` type — every
comparison against a possibly-ORM-sourced value uses `==`, never `is`.**
A row found live in a session's identity map keeps its enum attribute as
the genuine Python enum instance; a row freshly materialized by a plain
`SELECT` gets back a raw `str` for that same column. This lesson came
from `services/multi-cluster-management-service`'s own hard-won
incident (see its README/`AI_MEMORY.md`) and was applied proactively
here from the very first line of every engine — no defect of this class
was found in this build.

**A domain field must never reuse one of `BaseEntityMixin`'s reserved
column names** (`id`, `created_at`, `updated_at`, `is_active`,
`organization_id`, `project_id`, `version`). This build hit the
`is_active` collision for real: `EdgeConfiguration` originally named its
"is this the currently-applied revision" flag `is_active`, which is the
exact name `SoftDeleteMixin` reserves as *every* repository's
soft-delete flag. Setting it to `False` to mark a superseded revision
silently soft-deleted that row out of every future query — caught by an
integration test asserting the superseded row was still visible via
`list_for_device()`, not by MyPy (both fields are `bool`, so there was
no type mismatch to catch). Renamed to `is_current`. See `AI_MEMORY.md`
for the full narrative.

---

## What it does

### Site & location hierarchy (`app/models/sites.py`, `app/services/sites.py`)

One registered facility (`EdgeSite`) containing an arbitrary-depth
physical hierarchy (`EdgeLocation`, nested via `parent_location_id`) —
factory → plant → building → floor → production line → cell → zone →
rack → room, or a standalone `GEO_LOCATION` leaf for a site with no
facility structure at all (a remote kiosk, a vehicle).

### Device registration & lifecycle (`app/devices/`, `app/registration/`, `app/services/devices.py`)

Discovery → registration → provisioning → configuration → active, with
maintenance/suspend as reversible detours from `ACTIVE` and
retiring → secure-wiping → retired as the one-way exit; `FAILED` can
retry back to `REGISTERED` or retire outright. Enrollment credential
validation (`app/registration/engine.py`) checks only what this
service's own row can know — a non-empty reference and a not-yet-expired
date — never the secret itself, which is secrets-management-service's
job, matching the posture `services/multi-cluster-management-service`
takes with `ClusterCredential.credential_ref`.

### Health monitoring (`app/health/`)

Per-component readings (CPU, memory, storage, temperature, power,
network) rolled up into one overall device verdict against two
independent thresholds (degraded, unhealthy). A device whose
`last_seen_at` has gone stale is reported offline regardless of its last
self-reported status.

### Offline-first synchronization (`app/synchronization/`, `app/store_forward/`)

Sync outcome classification, conflict resolution by an explicit strategy
(server-wins / device-wins / last-write-wins / manual — manual never
auto-resolves), retry eligibility (only `FAILED` is retryable; a
`CONFLICT` needs resolution first), and exponential store-and-forward
backoff, capped, never unbounded.

### OTA & firmware (`app/ota/`, `app/services/firmware.py`)

Version-skew validation against the firmware catalog (refuses a
downgrade, a no-op, or a jump exceeding the configured maximum skew) and
a rollback recommendation triggered only by an *explicit* post-update
verification failure — never by verification simply never having run.

### Edge AI (`app/edge_ai/`)

A model may only be promoted from `STAGED` to `DEPLOYED`, never
re-promoted once deployed (a later rollback references the superseded
deployment via `rollback_of_id` instead). Inference target selection
prefers GPU when available or required.

### Industrial protocols (`app/protocols/`)

Connectivity state tracking (OPC UA, MQTT, Modbus TCP/RTU, BACnet,
PROFINET, EtherNet/IP, DNP3, IEC 61850, Redfish, SNMP) — classification
only, no live protocol drivers; see *Scope boundary*.

### Digital twins (`app/digital_twins/`)

A pure `desired-hash` vs `live-hash` comparison, reported `IN_PROGRESS`
during an active sync regardless of what the hashes currently say —
mirroring `services/multi-cluster-management-service`'s own GitOps sync
classification discipline.

### Configuration (`app/configuration/`)

Versioned key/value configuration per device; rollback validation
refuses an unknown revision and a no-op rollback to the revision already
active.

### Analytics (`app/analytics/`)

Fleet-wide success/availability rates, every one `None` on a zero
denominator, never `0.0` or `1.0`.

---

## Scope boundary

Per docs/067's own "DO NOT IMPLEMENT" section, this service does **not**
run PLC firmware, industrial control logic, a real-time operating
system, or vendor-specific hardware drivers. Consistent with that
boundary, industrial protocol support is implemented as real, tested
connectivity-state tracking with **no live protocol client wired up**,
matching the "declared seam" pattern `services/backup-dr-service`
established for MinIO/target-specific I/O and
`services/multi-cluster-management-service` established for
GitOps/service-mesh/federation:

- **Industrial protocols** (`app/protocols/engine.py`): connectivity
  classification is real and tested; there are no OPC UA/MQTT/Modbus/
  BACnet/PROFINET/EtherNet-IP drivers.
- **Digital twins** (`app/digital_twins/engine.py`): sync-state
  classification is real; there is no live twin-platform integration.
- **Remote access** (`POST /edge/devices/{id}/remote-access`): grants or
  refuses a session based on this service's own `is_online` signal and
  records it on the audit trail — it does not open a live tunnel/VPN
  session to the device, since this build holds no device-side transport
  credentials capable of doing so.

---

## REST API

13 routes under `/edge`, plus `/health`, `/liveness`, `/readiness`,
`/metrics` (Prometheus), `/docs` (OpenAPI). Every route derives its
tenant from the caller's JWT (`organization_id` claim) — never from a
query or body parameter.

| Method | Path                                    | Purpose                                                              |
| ------ | ---------------------------------------- | --------------------------------------------------------------------- |
| GET    | `/edge/health`                           | Fleet-wide device health snapshot                                     |
| GET    | `/edge/statistics`                       | Rolled-up fleet statistics                                            |
| GET    | `/edge/reports`                          | Generated reports, newest first                                       |
| GET    | `/edge/sites`                            | List sites                                                            |
| POST   | `/edge/sites`                            | Register a site (administrator role required)                         |
| GET    | `/edge/devices`                          | List devices                                                          |
| POST   | `/edge/devices`                          | Register a device (administrator role required; `409` on an unusable enrollment credential) |
| GET    | `/edge/devices/{id}`                     | Get one device                                                        |
| PUT    | `/edge/devices/{id}`                     | Update a device (administrator role required)                          |
| DELETE | `/edge/devices/{id}`                     | Start retiring (administrator role required; `409` if the current lifecycle state cannot reach `RETIRING`) |
| POST   | `/edge/devices/{id}/provision`           | Advance a device's lifecycle to a given target state (`409` if refused) |
| POST   | `/edge/devices/{id}/sync`                | Run a synchronization                                                  |
| POST   | `/edge/devices/{id}/update`              | Plan an OTA update (administrator role required)                        |
| POST   | `/edge/devices/{id}/remote-access`       | Request remote access (administrator role required; granted only while the device is online) |

## Background workers

Five jobs, all **leader-elected** through `shared_core.scheduler` — each
is pure database work with no per-replica state:

| Worker                  | Default interval | What it does                                                          |
| ------------------------ | ----------------- | ------------------------------------------------------------------------ |
| Health sweep                | 60s            | Recomputes overall health from readings; marks stale devices offline      |
| Synchronization sweep           | 300s       | Fails any synchronization stuck `IN_PROGRESS` past the staleness window     |
| Update reconcile                    | 1800s  | Fails any OTA update stuck in-progress past the staleness window            |
| Protocol sweep                          | 300s | Reclassifies every protocol endpoint's connectivity against current time      |
| Statistics rollup                          | 900s | Idempotent per-window fleet statistics rollup                                  |

## Configuration

Every fleet threshold is a configuration field
(`app/config/settings.py`), never a compiled-in constant.

Key environment variables (prefix `AIIOS_EDGE_MANAGEMENT_SERVICE_` for
service-specific fields; shared infrastructure fields use the
platform-wide `AIIOS_DATABASE_*` / `AIIOS_REDIS_*` / `AIIOS_RABBITMQ_*`
prefixes):

- `PORT` (default `8038`), `JWT_PUBLIC_KEY_PATH`
- `STALE_DEVICE_THRESHOLD_MINUTES`, `HEALTH_DEGRADED_COMPONENT_THRESHOLD`, `HEALTH_UNHEALTHY_COMPONENT_THRESHOLD`
- `SYNC_RETRY_MAX_ATTEMPTS`, `SYNC_STALE_THRESHOLD_MINUTES`
- `MAX_SUPPORTED_FIRMWARE_SKEW`, `UPDATE_DEFAULT_STRATEGY`
- `AI_MODEL_HEALTH_CHECK_INTERVAL_SECONDS`
- `WORKERS_ENABLED` plus a `*_SECONDS` interval per worker

## Running locally

```bash
cd services/edge-management-service
uv sync
uv run alembic upgrade head
uv run uvicorn main:app --host 0.0.0.0 --port 8038
```

Requires PostgreSQL (database `aiios_edge`), Redis, and RabbitMQ
reachable per the `AIIOS_*` environment variables. **Every AI-IOS
service shares one Postgres instance but owns its own database and its
own Alembic version table** (`alembic_version_edge_management_service`).

## Testing

```bash
uv run python -m pytest tests/ --cov=app --cov-report=term-missing
```

216 tests, 97.3% coverage. Every test that touches persistence runs
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
