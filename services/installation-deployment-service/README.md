# Installation & Deployment Service

Enterprise Installation & Deployment Service (Prompt 075) — infrastructure
validation, platform installation, configuration, deployment, upgrades,
rollback, lifecycle management, and Day-0/Day-1 operations across
development, enterprise production, cloud-native, on-premises, hybrid
cloud, edge, and fully air-gapped deployments.

Port `8046`. Database `aiios_installation_deployment`. Redis db `48`.

## Ideas that shape everything here

**This service is a control plane, not an installer.** docs/075's own
"DO NOT IMPLEMENT" list excludes an Operating System Installer,
Container Runtime, Kubernetes Distribution, and Cloud Provider
Deployment Services. This build models and orchestrates the *records*
of installation/deployment/upgrade/rollback activity — sessions, jobs,
history, versions, status — and validates what it can validate from
inside its own process; it never shells out to `kubectl`, `helm`, or a
cloud provider's own API. The one genuinely-implemented execution path
is self-signed certificate generation (`app/tls/engine.py`), because
that is pure Python the process can do for itself with no external
tool dependency.

**Every route requires an administrator role — a full return to
069-071's routing shape.** Unlike `services/developer-portal-service`
or `services/public-api-platform` (072-074), there is no "caller acting
on their own account" shape for installing, deploying, upgrading, or
rolling back a platform: it is inherently an operator action. All 10
REST routes sit behind `require_administrator`, the same
administrator-heavy routing `services/administration-portal-service`
(Prompt 070) established.

**Pre-flight and post-install verification are caller-reported-outcome
services, like `services/developer-portal-service`'s `WebhookTestService`.**
This process can only genuinely probe infrastructure it already holds
a live connection to (its own database, its own cache); everything
else docs/075 names (CPU, memory, OS, DNS, firewall, SELinux, and so
on) would need an installed host agent this build does not implement.
`PreflightService.record_result` and `VerificationService.record_result`
are therefore the primary paths: the caller (an installer agent, a
CLI, or this process's own real database/cache probe) reports what it
found, and this service records, aggregates (worst-of-N via
`app.preflight.engine.aggregate_check_results`, reused unmodified by
`app.verification.engine`), and notifies on `FAILED`.

**A new bug class from Prompt 074 was checked for proactively and
avoided twice more.** Both edge-triggered notifications in this build
— Certificate Expiring (`CertificateExpirySweepWorker`) and Upgrade
Available (`UpgradeAvailabilitySweepWorker`) — were designed from the
start to notify only on a genuine transition (valid → expiring; a
version's own `released_at` still inside its lookback window), not on
every tick for as long as the condition holds. Verified directly in
this build's own worker tests
(`test_notifies_only_on_transition_to_expiring`,
`test_does_not_notify_once_outside_lookback_window`) and confirmed
live in Docker.

**Secrets and private keys are never persisted.** `GeneratedSecret`
stores only a masked display form (`app.secrets.engine.mask_for_display`,
built on `shared_core.security.secrets.mask_secret`); a TLS private key
is returned to the caller exactly once, at issuance, and this
service's own database never sees it — `TlsCertificate` stores only
the public certificate material. Rotating a secret retires the old row
to `ROTATED` and issues a brand-new `ACTIVE` row under the same name,
rather than overwriting history in place.

**Rollback only ever targets a version this installation has actually
seen.** `app.rollback.engine.can_rollback_to` refuses a target version
that isn't both older than the current one *and* present in this
organization's own `deployment_versions` history — rollback restores a
previously known-good state, it never jumps to an arbitrary version.

## Architecture

- `app/models/` — 21 tables across 8 files: `deployment.py`
  (DeploymentProfile, DeploymentTarget, DeploymentInventory,
  DeploymentJob, DeploymentHistory, DeploymentVersion,
  DeploymentArtifact, DeploymentStatusRecord — the live status board,
  distinct from `deployment_history`'s append-only log),
  `installation.py` (InstallationSession, InstallationLog),
  `validation.py` (PreflightResult, DependencyCheck),
  `configuration.py` (ConfigurationProfile), `secrets_tls.py`
  (TlsCertificate, GeneratedSecret), `upgrade_rollback.py`
  (UpgradeHistory, RollbackHistory), `verification.py`
  (VerificationResult), `reporting.py` (DeploymentStatistic,
  DeploymentReport, DeploymentAudit).
- 10 pure engines, each hand-verified before any pytest was written
  (49 checks, zero defects): `app/installer/engine.py` (session
  lifecycle, two terminal states), `app/deployment/engine.py` (the
  shared job lifecycle reused by every job type — install, deploy,
  upgrade, rollback), `app/preflight/engine.py` (worst-of-N check
  aggregation, reused by verification), `app/dependencies/engine.py`
  (`SemanticVersion` numeric parsing/comparison, reused by upgrade and
  rollback), `app/upgrade/engine.py` (forward-path validation),
  `app/rollback/engine.py` (known-version-only target validation),
  `app/verification/engine.py` (reuses preflight's aggregation),
  `app/tls/engine.py` (self-signed certificate generation, expiry
  classification), `app/secrets/engine.py` (credential generation,
  rotation staleness), `app/analytics/engine.py` (success rate,
  average duration, rollback frequency).
- `app/services/` — one service per table-group plus
  `notifications.py` (`DeploymentNotifier` + `NotifyingPublisher`),
  `audit.py` (the single write path for `deployment_audit`),
  `bundle.py` (the shared repository bundle). `DeploymentJobService`
  is the one generic job engine every job type builds on;
  `UpgradeService` and `RollbackService` layer their own
  version-validated orchestration and specific events on top of it.
- `app/api/deployment.py` — the 10 REST routes exactly as docs/075
  lists them, every one gated behind `require_administrator`.
- `app/workers/` — 5 leader-elected background jobs: installation
  session expiry sweep, deployment job timeout sweep (shared across
  every job type), certificate expiry sweep (edge-triggered), statistics
  rollup, upgrade availability sweep (edge-triggered via lookback
  window).
- 9 domain events (`app/events/domain_events.py`), 8 notification
  kinds (`app/services/notifications.py`) — 1 fanned from an event
  (`RollbackCompleted` → Rollback Completed), 6 called directly, 1 a
  declared seam (Infrastructure Issue, the same shape
  `services/developer-portal-service`'s Security Notice took).

## Testing

137 tests (49 engine, 21 repository, 26 service, 8 worker, 10 API, 21
deps/notifications/registrar, plus 2 smoke tests) at 97.82% coverage,
against real PostgreSQL and Redis. Ruff, Black, and MyPy (scoped to
`app/` + `main.py`) all clean.

Live Docker e2e confirmed: all 5 workers registered and leader-elected
on startup; health/readiness real; the full install → validate →
deploy → upgrade lifecycle exercised end-to-end through real HTTP
against the running container with real RS256-signed JWTs; **the
deployment job timeout sweep worker confirmed to autonomously fail a
manually-backdated stuck job on a subsequent scheduled tick** — watched
directly via `psql` and the worker's own structured logs (`failed: 0`
on the tick immediately after the job started, `failed: 1` on the next
tick after backdating), correctly leaving a second, genuinely fresh job
untouched; `deployment_history` confirmed recording the full
started → failed lifecycle; RBAC confirmed (403 non-admin on
`/install/start`, 401 no token); database truncated and container
removed after.
