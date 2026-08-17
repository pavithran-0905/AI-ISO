# Upgrade Framework Service

Enterprise Upgrade Framework Service (Prompt 076) — orchestrating safe,
automated, policy-driven upgrades across the AI-IOS platform, managed
infrastructure, plugins, edge devices, cloud resources, and Kubernetes
environments, with zero-downtime upgrades, compatibility validation,
health-gated deployments, and automatic rollback.

Port `8047`. Database `aiios_upgrade_framework`. Redis db `49`.

## Ideas that shape everything here

**A control plane over the upgrade lifecycle, not an execution
engine.** docs/076's own "DO NOT IMPLEMENT" list excludes Operating
System Package Managers, Kubernetes Upgrade Controllers, Cloud
Provider Upgrade Engines, and Third-party Release Management Systems.
Every "engine" this build ships models and orchestrates *records* of
upgrade/compatibility/migration/rollback activity and computes what it
genuinely can from data it already holds (semantic version comparison,
risk scoring, wave planning); it never invokes `apt`, a Kubernetes
upgrade controller, or a cloud provider's own upgrade API.

**One shared, event-free job engine; two distinct event
vocabularies on top.** `UpgradeJobService` is pure status transitions
plus append-only history, with no events of its own — mirroring
`services/installation-deployment-service`'s own `DeploymentJobService`
precedent (Prompt 075), except that docs/076 names ``UpgradeStarted``/
``UpgradeCompleted``/``UpgradeFailed`` and ``RollbackStarted``/
``RollbackCompleted`` as *two entirely separate* event pairs rather
than one generic "job" pair. `UpgradeExecutionService` layers the
upgrade-specific events on top of the shared engine;
`RollbackService` layers the rollback-specific ones — same underlying
state machine, different vocabulary, decided directly from how the
two prompts' own specs differ on this one point.

**Health-Gated Upgrades' "Automatic Pause" is genuinely implemented,
not just declared.** `HealthGateEnforcementWorker` autonomously fails
(pauses) any `RUNNING` upgrade job that has accumulated a `FAILED`
verification result — confirmed live in this build's own Docker e2e
run, firing on its own 60-second schedule with no manual trigger. An
actual rollback remains a separate, explicit `POST /rollback` action;
this worker only detects and pauses, the same separation of concerns
`services/installation-deployment-service`'s own rollback framework
established.

**Two edge-triggered notification workers, following two established
lessons.** `ReleaseAdoptionSweepWorker` (Upgrade Available) reuses
Prompt 075's "notify only while the newer version's own `released_at`
still falls inside a lookback window" design; and the "add a properly
scoped repository method instead of degenerate arguments" lesson from
Prompt 074 was applied proactively throughout — every worker's own
organization discovery unions multiple genuinely relevant activity
sources rather than reaching for one convenient-but-wrong existing
query.

**Compatibility validation and dependency checks share one numeric
`SemanticVersion` implementation** (`app.compatibility.engine`, reused
unmodified by `app.dependencies.engine` and `app.rollback.engine`) —
one comparison implementation, not three, the same discipline
`services/installation-deployment-service` and
`services/public-api-platform` established for their own version
engines.

**Upgrade simulation persists nothing.** docs/076's own DATABASE
TABLES section has no simulation-result table, so `POST
/upgrade/simulate`'s risk assessment and duration estimate
(`app.simulation.engine`) are computed purely from the request body
and returned directly — the same "nothing to persist" shape
`services/installation-deployment-service`'s own dry-run capability
took (Prompt 075).

**Every route requires an administrator role.** Scheduling, running,
rolling back, or migrating an upgrade across a fleet is inherently an
operator action — the same administrator-heavy routing
`services/installation-deployment-service` (Prompt 075) and
`services/administration-portal-service` (Prompt 070) established.

## Architecture

- `app/models/` — 17 tables across 7 files: `releases.py`
  (ReleaseChannel, ReleaseVersion), `upgrade.py` (UpgradePlan,
  UpgradeJob, UpgradeHistory, UpgradeTarget, UpgradeResult,
  UpgradeDependency), `compatibility.py` (CompatibilityMatrixEntry),
  `migrations.py` (MigrationHistory, ConfigurationMigration,
  PluginMigration), `rollback.py` (RollbackHistory), `verification.py`
  (VerificationResult), `reporting.py` (UpgradeStatistic,
  UpgradeReport, UpgradeAudit).
- 10 pure engines, each hand-verified before any pytest was written
  (43 checks, zero defects): `app/upgrade/engine.py` (the shared job
  lifecycle), `app/compatibility/engine.py` (`SemanticVersion`,
  reused by 2 other engines), `app/dependencies/engine.py`,
  `app/rollback/engine.py`, `app/simulation/engine.py` (risk
  assessment, duration estimation), `app/health/engine.py` (weighted
  health scoring), `app/verification/engine.py` (worst-of-N
  aggregation), `app/migrations/engine.py` (reverse-order rollback
  planning), `app/fleet/engine.py` (wave-based target chunking),
  `app/analytics/engine.py` (success rate, rollback rate, channel
  adoption distribution).
- `app/services/` — one service per table-group plus
  `notifications.py` (`UpgradeNotifier` + `NotifyingPublisher`),
  `audit.py` (the single write path for `upgrade_audit`),
  `bundle.py` (the shared repository bundle).
- `app/api/upgrade.py` — the 10 REST routes exactly as docs/076 lists
  them, every one gated behind `require_administrator`.
- `app/workers/` — 5 leader-elected background jobs: upgrade job
  timeout sweep, migration timeout sweep, release adoption sweep
  (edge-triggered), health gate enforcement (autonomous auto-pause),
  statistics rollup.
- 9 domain events (`app/events/domain_events.py`), 7 notification
  kinds (`app/services/notifications.py`) — 1 fanned from an event
  (`ReleasePublished` → Release Published), 6 called directly.

## Testing

125 tests (48 engine, 17 repository, 22 service, 7 worker, 9 API, 20
deps/notifications/registrar, plus 2 smoke tests) at 97.31% coverage,
against real PostgreSQL and Redis. Ruff, Black, and MyPy (scoped to
`app/` + `main.py`) all clean.

Live Docker e2e confirmed: all 5 workers registered and leader-elected
on startup; health/readiness real; the full plan → upgrade →
job/history listing lifecycle exercised end-to-end through real HTTP
against the running container with real RS256-signed JWTs; **the
health gate enforcement worker confirmed to autonomously auto-pause a
`RUNNING` upgrade job on its very next scheduled tick after a `FAILED`
verification result was recorded** — watched directly via `psql` and
the worker's own structured logs (`paused: 1`), with `upgrade_history`
confirming the full `started -> failed` lifecycle and the job's own
`error_message` set to `"Health gate failed: automatic pause
triggered."`, never manually triggered; RBAC confirmed (403 non-admin
on `/channels`, 401 no token); database truncated and container
removed after.
