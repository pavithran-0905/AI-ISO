# Production Hardening Framework

Enterprise Production Hardening Framework Service (Prompt 079) —
validating, securing, certifying, and enforcing production readiness
across every AI-IOS component before release.

Port `8050`. Database `aiios_production_hardening_framework`. Redis db `52`.

## Ideas that shape everything here

**A control plane over hardening and certification records, not a
security scanner.** docs/079's own "DO NOT IMPLEMENT" list excludes OS
security products, commercial vulnerability scanners, hardware TPM
firmware, and cloud provider security services. Every engine and
service here models and evaluates *records* of hardening runs, security
findings, vulnerability scans, compliance controls, and readiness
checks that some external tool (a CIS benchmark runner, a scanner, an
audit process) reports in — it never scans a host or a container image
itself.

**A shared, event-free job engine.** `app.hardening.engine`
(`HardeningRunStatus` PENDING→RUNNING→{SUCCEEDED,FAILED},
`validate_transition`, `is_job_stuck`) is the same proven shape every
prior AI-IOS service in this build (076-078) established. Unlike
Prompt 077's `TestRunService`, docs/079 names only one completion
event (`HardeningCompleted`, not a Started/Completed/Failed triple),
matching Prompt 078's own `BenchmarkCompleted` shape — it fires on
every terminal state regardless of outcome.

**`GET /production-readiness` computes live and persists nothing.**
docs/079's own DATABASE TABLES section has no dedicated table for this
endpoint's own result, so `ProductionReadinessService.compute()`
aggregates the most recent hardening results, compliance evaluations,
operational readiness checks, and disaster recovery checks into an
equal-weighted score, the same "nothing to persist" shape
`services/upgrade-framework-service`'s own dry-run simulate endpoint
took (Prompt 076). `ProductionReadinessSweepWorker` reuses the exact
same computation to decide when to publish `ProductionReady`.

**The `ProductionReady` edge-trigger is signal-freshness-based, not
state-transition-based, because there is no dedicated readiness-state
table to track a transition against.** Every other edge-triggered
worker in this codebase (077's `FlakyTestDetectionWorker`, 078's
`RegressionSweepWorker`) uses the same underlying idea: only re-evaluate
and re-announce when something genuinely new has happened. Here, that
means the worker only recomputes an organization's readiness score
when at least one of its four underlying signal sources (hardening
result, compliance evaluation, operational readiness check, disaster
recovery check) has a record newer than the lookback window — an
organization sitting at a stale, already-known readiness level does
not get re-evaluated (or re-notified) on every tick.

**Certificate expiry uses a persisted `is_expiring` flag; certification
expiry needs none.** `CertificateExpirySweepWorker` follows
`services/installation-deployment-service`'s own precedent (Prompt 075)
exactly: a boolean flag on the row itself is the edge-trigger, set once
and never reset, so a certificate sitting in its warning window for
weeks notifies exactly once. `CertificationExpirySweepWorker` needs no
such flag at all — once a certification leaves `GRANTED` status
(transitioning to `EXPIRED`), the worker's own `GRANTED`-only query
stops seeing it, which is inherently edge-triggered without any extra
state.

**Risk score is always computed server-side, never trusted from the
caller.** `POST /certifications` accepts three caller-measured rates
(hardening, compliance, readiness) but `ProductionCertificationService`
itself computes the resulting risk score and grant/deny decision via
`app.certification.engine.compute_risk_score`/`should_grant` — a route
cannot request a specific risk score or force a grant.

**One fanned notification, six direct.** `VulnerabilityDetected` is
the only one of docs/079's seven notification kinds wired through
`NotifyingPublisher` (into Critical Vulnerability, and only when the
recorded severity is itself `CRITICAL`) — the same "1 fanned, N direct"
shape every AI-IOS service in this build uses. The other six are
called directly by the code that observes the underlying fact:
Certificate Expiring and Certification Expired by their own
edge-triggered sweep workers, Hardening Failed by
`HardeningRunService` on a failed terminal state, Certification
Granted by `ProductionCertificationService` on grant, Compliance
Failure by `ComplianceService` on a non-compliant evaluation,
Operational Risk by `OperationalReadinessService` on a failed check.

**Every route requires an administrator role.** Hardening execution,
security findings, and certification decisions are internal
engineering signals, not customer-facing data — the same
administrator-heavy routing every adjacent infrastructure-framework
service in this build (075-078) established.

**Most REST routes are read-only by design.** Of the 11 routes
docs/079 lists, only `POST /hardening/run` (start a run) and
`POST /certifications` (evaluate and grant/deny) mutate anything;
hardening profiles have no creation route at all — they are seeded
internally (or, in tests, directly) — the same "no route for
tables workers/internal tooling own" precedent
`services/performance-benchmark-framework` established for baselines
(Prompt 078).

## Architecture

- `app/models/` — 16 tables across 11 files: `hardening_definitions.py`
  (HardeningProfile), `hardening_execution.py` (HardeningRun,
  HardeningResult), `security_findings.py` (SecurityFinding),
  `vulnerabilities.py` (VulnerabilityScan), `supply_chain.py`
  (SbomCatalog, SignedArtifact), `runtime_protection.py`
  (RuntimeProtectionEvent), `compliance.py` (ComplianceResult),
  `certification.py` (ProductionCertification), `readiness.py`
  (OperationalReadiness, DisasterRecoveryCheck), `certificates.py`
  (CertificateInventoryEntry), `reporting.py` (HardeningStatistic,
  HardeningReport, HardeningAudit).
- 10 pure engines, each hand-verified before any pytest was written
  (43 checks, zero defects): `app/hardening/engine.py` (the shared job
  lifecycle), `app/security/engine.py` (risk-score-to-severity
  classification), `app/vulnerability/engine.py` (severity-scaled
  remediation SLA), `app/compliance/engine.py` (compliance rate),
  `app/certification/engine.py` (risk scoring, grant decision,
  expiration), `app/operational_readiness/engine.py` (readiness
  rate), `app/disaster_recovery/engine.py` (RTO/RPO validation),
  `app/certificates/engine.py` (expiry window detection),
  `app/runtime_protection/engine.py` (critical-event classification),
  `app/analytics/engine.py` (hardening score, equal-weighted
  four-way production readiness score).
- `app/services/` — one service per table-group plus
  `production_readiness.py` (the shared live-aggregate computation),
  `notifications.py` (`HardeningNotifier` + `NotifyingPublisher`),
  `audit.py` (the single write path for `hardening_audit`),
  `bundle.py` (the shared repository bundle).
- `app/api/hardening.py` — the 11 REST routes exactly as docs/079
  lists them, every one gated behind `require_administrator`.
- `app/workers/` — 5 leader-elected background jobs: hardening run
  timeout sweep, certificate expiry sweep (edge-triggered via a
  persisted flag), certification expiry sweep (inherently
  edge-triggered via status), production readiness sweep
  (edge-triggered via signal freshness), statistics rollup.
- 8 domain events (`app/events/domain_events.py`), 7 notification
  kinds (`app/services/notifications.py`) — 1 fanned from an event
  (`VulnerabilityDetected` → Critical Vulnerability, severity-gated),
  6 called directly.

## Testing

131 tests (45 engine, 14 repository, 22 service, 9 worker, 13 API, 26
deps/notifications, plus 2 smoke tests) at 97.00% coverage, against
real PostgreSQL and Redis. Ruff, Black, and MyPy (scoped to `app/` +
`main.py`) all clean.

Live Docker e2e confirmed: all 5 workers registered on startup;
health/readiness real; a hardening profile seeded and a run started
through real HTTP with real RS256-signed JWTs; **three data-writing
workers confirmed firing fully autonomously on the very next scheduled
tick after their respective source rows were backdated/seeded via
`psql`** — the hardening run timeout sweep worker failed a stuck run
(`failed: 1`), the certificate expiry sweep worker flagged a
newly-in-window certificate (`notified: 1`, `is_expiring` persisted
`true`), and the certification expiry sweep worker expired an overdue
certification (`expired: 1`) — all watched directly via the
container's own structured logs and confirmed via `psql`, never
manually triggered; RBAC confirmed (401 no token, 403 non-admin role,
200 admin); database truncated and container removed after.
