# SDK & CLI Service

Generating, maintaining, versioning, documenting, and distributing
official SDKs and a cross-platform CLI for every AI-IOS capability.

Implements `docs/071_Enterprise_SDK_&_CLI_Service.md`.

- **Port** 8042 · **Database** `aiios_sdk_cli` · **Redis db** 44

This service is the tracking, orchestration, and code-generation
backend for SDK and CLI artifacts, not a real multi-language SDK
codebase, a real CLI binary, or a package registry — see *Scope
boundary* below for exactly where it stops.

---

## The ideas that shape everything here

**A domain field must never reuse one of `BaseEntityMixin`'s reserved
column names** (`id`, `created_at`, `updated_at`, `is_active`,
`organization_id`, `project_id`, `version`) — and this service found
that lesson the hard way rather than avoiding it. `SdkVersion`,
`CliVersion`, and `CliPlugin` all naturally wanted a field literally
called `version` (a semver string like `"1.2.3"`); integration testing
caught the collision immediately (`entity.version += 1` inside
`BaseRepository.update()`'s optimistic-locking increment raised
`TypeError: can only concatenate str (not "int") to str` the moment any
of the three was updated), since `version` is already
`BaseEntityMixin`'s own reserved integer optimistic-locking column.
Fixed by renaming the domain field to `version_label` everywhere,
matching the same naming precedent
`services/cloud-management-service`'s `CloudCatalogItem.version_label`
already established in Prompt 068 for the identical situation — the
REST API itself still calls the field `version`, since only the ORM
column needed to change.

**Enum-typed columns are plain `String`, not a SQL `Enum` type — every
comparison *and every `.value` access* against a possibly-ORM-sourced
value goes through the enum class first.** A second real defect,
caught by this service's own live e2e-adjacent API tests: a route read
`plugin.status.value` directly off a repository-freshly-loaded row,
where `plugin.status` comes back as a plain `str` rather than the
`PluginStatus` instance the type annotation promises, raising
`AttributeError: 'str' object has no attribute 'value'`. Fixed by
coercing through `PluginStatus(plugin.status)` before use -- the same
class of bug `services/multi-cluster-management-service` first
documented, now confirmed to bite `.value` access, not just `==`/`is`
comparison.

**A generator or version-parsing failure is a client error, not an
unhandled 500.** `POST /sdk/generate`'s first draft let
`app.generator.engine`'s own `ValueError` (an unrecognized field type,
an invalid identifier) propagate straight out of the route unguarded;
caught by an API test expecting a structured 4xx and instead getting a
raw exception through the ASGI transport. Fixed by catching `ValueError`
at the route boundary and re-raising as `shared_core.exceptions.ValidationError`.

**Semantic version comparison is always numeric, never lexical.**
`app.versioning.engine.parse_version` exists specifically so
`"9.0.0" < "10.0.0"` compares correctly -- as strings that comparison
is false, which would make an update-available check silently wrong
for any double-digit version component.

**A statistics rollup window is `[window_start, window_end)` on the
*last completed* hour, not "everything ever."** An event timestamped
"right now" during the same tick that triggers a rollup correctly does
not appear until the *next* rollup -- proven directly in this service's
own worker tests by timestamping fixtures explicitly inside the
completed window rather than at `datetime.now()`.

---

## What it does

### SDK versions, packages, and downloads (`app/sdk/`, `app/services/sdk_versions.py`)

Per-language (`Python`/`TypeScript`/`Go`/`Java`/`.NET`) version
registration, a language catalog tracking each language's latest
version, distribution-channel package records
(PyPI/npm/Maven/NuGet/Go Modules/GitHub Releases/offline) with a
SHA-256 checksum and signed flag, and raw download-event recording —
publishing `SDKDownloaded`.

### SDK releases (`app/sdk/engine.py`, `app/services/sdk_releases.py`)

Release lifecycle draft → published → deprecated/yanked, publishing
`SDKReleased` on publication with `breaking_changes` carried in the
event payload so the notification layer can fan out to Breaking API
Changes without a second event.

### Code generation (`app/generator/`, `app/services/generator.py`)

Real, tested rendering of strongly typed model and enumeration stubs
for Python, TypeScript, and Go from a generator-neutral field/type
description — every field's type is looked up against an explicit
table, never guessed, and an unrecognized type or invalid identifier
is a hard, caught `ValueError`.

### CLI versions and updates (`app/cli/`, `app/services/cli_versions.py`, `app/services/cli_updates.py`)

Version registration (publishing `CLIReleased`), and update-attempt
recording through `PENDING → DOWNLOADING → APPLIED/FAILED` — the
outcome is reported by the caller, publishing `CLIDownloaded` only on
a successful `APPLIED` outcome. See *Scope boundary*.

### CLI plugins (`app/cli/plugins/`, `app/services/cli_plugins.py`)

Plugin lifecycle `AVAILABLE ⇄ INSTALLED → DEPRECATED/REMOVED`, with
`REMOVED → AVAILABLE` for reinstallation — publishing `PluginInstalled`
on install and `PluginUpdated` on every other transition.

### CLI profiles, sessions, and usage (`app/cli/profiles/`, `app/cli/authentication/`, `app/services/cli_profiles.py`, `app/services/cli_sessions.py`, `app/services/cli_usage.py`)

Named credential/context profiles with at-most-one-default enforcement
(`app/cli/profiles/engine.py` names exactly which other profiles must
be unset, never leaving a stale second default), session
authentication publishing `AuthenticationSucceeded` on success and
notifying Authentication Failure directly on failure (a failed attempt
is never persisted as a session), and raw command-execution recording.

### Packaging integrity (`app/packaging/`)

SHA-256 checksum computation and verification for every distributed
artifact — a package is verified against its own recorded checksum,
never trusted because it merely downloaded.

### Analytics, statistics & reports (`app/analytics/`, `app/services/statistics.py`, `app/services/reports.py`)

Success/adoption rates that are `None` on a zero denominator rather
than a misleading `0%`/`100%`, one idempotent per-window statistics
table serving both SDK and CLI activity (docs/071 names only
`cli_statistics`, not a separate `sdk_statistics`), and
SDK/CLI/usage/download/compatibility/plugin/audit report generation.

### Audit (`app/services/audit.py`)

The one write path onto the immutable `sdk_audit` trail — every other
service calls through here rather than constructing rows directly, so
SDK releases, CLI releases, plugin management, and authentication
events cannot quietly stop being recorded through a second,
slightly different construction path.

---

## Scope boundary

Per docs/071's own "DO NOT IMPLEMENT" section (Custom Programming
Languages, IDE Development, Third-party Package Managers, External
Build Systems), this service does **not** contain five real,
hand-written production SDK codebases, a real cross-platform CLI
binary, or integrations with PyPI/npm/Maven/NuGet/Go Modules
themselves. Consistent with that boundary, several capabilities are
implemented as real, tested decision and orchestration logic with **no
live external system wired up**, matching the "declared seam" pattern
`services/backup-dr-service` established in Prompt 065 and every
service since:

- **CLI updates** (`app/services/cli_updates.py`): the
  `PENDING → DOWNLOADING → APPLIED/FAILED` lifecycle is real and
  tested; `CliUpdateRequest.succeeded` is reported by the caller (the
  CLI's own updater, an operator) — this service records the outcome,
  it never downloads or applies a real CLI binary itself.
- **Code generation** (`app/generator/engine.py`): renders real
  Python/TypeScript/Go model and enum source text from a structured
  description; there is no live OpenAPI spec ingestion, template file
  system, or multi-file package scaffold — `POST /sdk/generate`'s
  `models` field is supplied directly by the caller, not parsed from a
  live `services/api-gateway-service` (Prompt 056) OpenAPI document.
- **Package distribution**: `SdkPackage.package_ref` and its checksum
  are real, tested records; there is no live publish to PyPI/npm/
  Maven/NuGet/Go Modules/GitHub Releases, and no real digital-signature
  infrastructure behind `is_signed` beyond the flag itself.
- **`auth_failure_count` is always `0`** in the statistics rollup — a
  failed CLI authentication attempt is notified directly but never
  persisted as a row anywhere in this service's own database, so there
  is nothing to truthfully count it from. Reported as a real zero, not
  omitted.

---

## REST API

12 routes, plus `/health`, `/liveness`, `/readiness`, `/metrics`
(Prometheus), `/docs` (OpenAPI). Every route derives its tenant from
the caller's JWT (`organization_id` claim) — never from a query or body
parameter. Several capability areas above (CLI version/plugin
registration outside install/remove, profile/session management)
have no route of their own beyond what docs/071's own REST APIs
section lists — the same "real logic, spec-scoped routing" pattern
`services/cloud-management-service` established in Prompt 068.

| Method | Path                          | Purpose                                                              |
| ------ | ------------------------------ | ------------------------------------------------------------------- |
| GET    | `/sdk`                         | List supported SDK languages                                          |
| GET    | `/sdk/releases`                  | List SDK releases                                                       |
| GET    | `/sdk/downloads`                   | List SDK downloads                                                       |
| POST   | `/sdk/generate`                      | Generate and publish an SDK version (administrator role required)         |
| GET    | `/cli`                                 | List CLI versions                                                          |
| GET    | `/cli/releases`                          | List CLI releases                                                            |
| POST   | `/cli/update`                              | Record a CLI update attempt (administrator role required)                      |
| POST   | `/cli/plugins/install`                       | Install a CLI plugin (administrator role required; `409` if refused)             |
| POST   | `/cli/plugins/remove`                          | Remove a CLI plugin (administrator role required; `409` if unknown/refused)         |
| GET    | `/cli/statistics`                                | CLI activity statistics                                                               |
| GET    | `/sdk/statistics`                                  | SDK activity statistics (same underlying window table as CLI statistics)                |
| GET    | `/sdk/reports`                                       | Generated reports, newest first                                                           |

## Background workers

Five jobs, all **leader-elected** through `shared_core.scheduler` — each
is pure database work with no per-replica state:

| Worker                     | Default interval | What it does                                                              |
| --------------------------- | ----------------- | ---------------------------------------------------------------------------- |
| Version compatibility sweep      | 3600s         | Notifies for SDK/CLI versions entering their deprecation warning window, and disables versions past it |
| CLI update check sweep               | 3600s     | Notifies for every still-enabled CLI version behind the latest                    |
| Plugin update sweep                      | 3600s | Notifies for installed plugins with a newer available version                       |
| Session expiry sweep                        | 300s  | Disables CLI sessions past their expiry                                               |
| Statistics rollup                              | 900s | Idempotent per-window SDK/CLI activity rollup                                           |

## Configuration

Every release/session threshold is a configuration field
(`app/config/settings.py`), never a compiled-in constant.

Key environment variables (prefix `AIIOS_SDK_CLI_SERVICE_` for
service-specific fields; shared infrastructure fields use the
platform-wide `AIIOS_DATABASE_*` / `AIIOS_REDIS_*` / `AIIOS_RABBITMQ_*`
prefixes):

- `PORT` (default `8042`), `JWT_PUBLIC_KEY_PATH`
- `SDK_DEPRECATION_WARNING_DAYS_BEFORE`, `CLI_DEPRECATION_WARNING_DAYS_BEFORE`
- `CLI_SESSION_MAX_AGE_MINUTES`
- `PLUGIN_UPDATE_CHECK_ENABLED`
- `WORKERS_ENABLED` plus a `*_SECONDS` interval per worker

## Running locally

```bash
cd services/sdk-cli-service
uv sync
uv run alembic upgrade head
uv run uvicorn main:app --host 0.0.0.0 --port 8042
```

Requires PostgreSQL (database `aiios_sdk_cli`), Redis, and RabbitMQ
reachable per the `AIIOS_*` environment variables. **Every AI-IOS
service shares one Postgres instance but owns its own database and its
own Alembic version table** (`alembic_version_sdk_cli_service`).

## Testing

```bash
uv run python -m pytest tests/ --cov=app --cov-report=term-missing
```

167 tests, 96.4% coverage. Every test that touches persistence runs
against a **real** PostgreSQL and Redis. Each test gets its own
SAVEPOINT-isolated database transaction (rolled back at teardown) and
its own tenant (`organization_id`).

Background workers are tested by calling `tick()` directly against a
real session factory bound to the test's own connection, using real
wall-clock time throughout. Live Docker e2e additionally confirmed all
five workers register and acquire scheduler leadership on startup, and
the statistics rollup worker fires autonomously on its own schedule —
never manually triggered — writing a real `cli_statistics` row
observed directly in the database.

Quality gates: `ruff check .`, `black --check .`, and
`mypy app/ main.py` (matching this project's CI convention of gating
`app/` and `main.py`, not `tests/`).
