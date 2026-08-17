# Testing & Quality Assurance Framework

Enterprise Testing & Quality Assurance Framework Service (Prompt 077)
— test orchestration, coverage tracking, quality gates, performance
and security testing, chaos engineering, synthetic monitoring, and
contract testing across the AI-IOS platform.

Port `8048`. Database `aiios_testing_quality_framework`. Redis db `50`.

## Ideas that shape everything here

**A pytest collection-glob collision, unique to this service.**
pytest's default `python_classes = Test*` glob collides head-on with
this service's own domain vocabulary — nearly every model and enum
here is legitimately named `TestSuite`, `TestCase`, `TestRun`,
`TestResult`, `TestEnvironmentType`, `TestType`, `TestRunStatus`, and
so on. Importing any of these under their real names into a test
module makes pytest try to collect them as test classes; since they
all define `__init__`/`__new__`, that raises
`PytestCollectionWarning: cannot collect test class 'X' because it has
a __init__/__new__ constructor` — and because this repo's
`pyproject.toml` sets `filterwarnings = ["error", ...]`, the warning
becomes a hard collection-time error that aborts the entire test file,
not just one test. **Every test module in this service aliases every
`Test*`-prefixed model, enum, service, and worker class at the import
statement itself** (`from app.models.test_definitions import TestSuite
as SuiteModel`, `from app.models.enums import TestRunStatus as
RunStatusEnum`, `from app.workers.test_run_timeout_sweep import
TestRunTimeoutSweepWorker as RunTimeoutSweepWorker`, etc.) — the bare
original name is never bound into a test module's namespace. A
follow-up lesson from applying this the first time: a blanket
find/replace across a file that also contains the name's own import
statement will corrupt that import (`TestRunStatus as RunStatus`
becomes the nonsensical `RunStatus as RunStatus`); alias at the import
line from the first draft rather than importing bare and renaming
afterward.

**A control plane over test/QA activity, not a test runner.**
docs/077's own "DO NOT IMPLEMENT" list excludes actual test execution
engines, CI/CD platforms, and browser automation frameworks. Every
engine and service here models and evaluates *records* of test runs,
results, coverage, performance, security, chaos, synthetic, and
contract outcomes that some external system (a CI pipeline, a test
runner, a chaos tool) reports in — it never runs a test itself.
`pipeline_results` is an explicit declared seam over whatever CI/CD
platform a deployment actually uses.

**A shared, event-free job engine, reused by two independently
event-vocabularied callers.** `app.pipeline.engine` (`TestRunStatus`
PENDING→RUNNING→{SUCCEEDED,FAILED}, `validate_transition`,
`is_job_stuck`) is pure status-transition logic with no events of its
own, shared unmodified by both `TestRunService` (which publishes
`TestStarted`/`TestCompleted`/`TestFailed` — docs/077 names these
explicitly) and `PipelineService` (which does not publish a domain
event for pipeline completion, since docs/077's own EVENTS list has no
dedicated Pipeline* pair — it calls `notify_pipeline_failed` directly
instead). The same shape `services/upgrade-framework-service`
established for its own `UpgradeJobService`/`RollbackService` split
(Prompt 076).

**Caller-reported-outcome services, because this process cannot
genuinely run a security scan, a chaos experiment, or a load test
itself.** `SecurityService`, `ChaosService`, `SyntheticCheckService`,
`ContractTestService`, `PerformanceService`, and `BenchmarkService` all
record and classify an outcome the caller supplies, using a pure
engine (`classify_security_result`, `classify_chaos_result`,
`classify_contract_compatibility`, `is_performance_regression`,
`is_benchmark_regression`) rather than probing anything live — the
same shape every adjacent infrastructure-framework service in this
build (075, 076) established for capabilities beyond a database/cache
connection this process actually holds.

**A self-contained `SemanticVersion` engine, copied independently
rather than shared across services.** `app.contract.engine` has its
own `MAJOR.MINOR.PATCH` parser (tolerating a `v` prefix and an ignored
pre-release suffix) for provider/consumer contract compatibility
classification — the same proven shape `services/installation-deployment-service`
(Prompt 075) and `services/upgrade-framework-service` (Prompt 076)
each keep their own copy of, since AI-IOS services never import each
other's application code.

**One fanned notification, six direct.** `QualityGateFailed` is the
only one of docs/077's seven notification kinds wired through
`NotifyingPublisher` (which forwards every event unchanged and
opportunistically notifies for this one). The other six — Pipeline
Failed, Coverage Dropped, Performance Regression, Security Issue,
Flaky Test Detected, Benchmark Regression — are called directly by the
code that observes the underlying fact, since none of them have a
dedicated domain event in docs/077's own EVENTS list.

**Two edge-triggered workers, both driven off an existing timestamp
column rather than a dedicated "already notified" table** (docs/077's
own DATABASE TABLES section has none): `FlakyTestDetectionWorker`
looks at each test case's own latest result's `created_at`, and
`CoverageDropSweepWorker` looks at each coverage type's own latest
report's `created_at` — both only notify while that timestamp still
falls inside a lookback window (twice the worker's own sweep
interval), so a case or coverage type stuck in a bad state does not
re-notify on every tick.

**Every route requires an administrator role.** Test results, security
findings, and quality-gate outcomes are internal engineering signals,
not customer-facing data — the same administrator-heavy routing
`services/installation-deployment-service` (Prompt 075) and
`services/upgrade-framework-service` (Prompt 076) established for
their own adjacent infrastructure frameworks.

## Architecture

- `app/models/` — 19 tables across 10 files: `test_definitions.py`
  (TestSuite, TestCase), `environments.py` (TestEnvironment,
  TestDataSet, MockService), `test_execution.py` (TestRun,
  TestResult), `quality_gates.py` (QualityGate), `coverage.py`
  (CoverageReport), `performance.py` (PerformanceResult,
  BenchmarkResult), `security_chaos.py` (SecurityResult, ChaosResult),
  `synthetic_contract.py` (SyntheticCheck, ContractTest), `pipeline.py`
  (PipelineResult — the declared CI/CD seam), `reporting.py`
  (QaStatistic, QaReport, QaAudit).
- 10 pure engines, each hand-verified before any pytest was written
  (51 checks, zero defects): `app/pipeline/engine.py` (the shared job
  lifecycle), `app/quality_gates/engine.py`, `app/coverage/engine.py`,
  `app/performance/engine.py`, `app/benchmark/engine.py`,
  `app/security/engine.py`, `app/chaos/engine.py`,
  `app/synthetic/engine.py`, `app/contract/engine.py`
  (`SemanticVersion`), `app/analytics/engine.py` (pass/failure/flaky
  rate, equal-weighted quality score, `is_flaky`).
- `app/services/` — one service per table-group plus
  `notifications.py` (`QaNotifier` + `NotifyingPublisher`),
  `audit.py` (the single write path for `qa_audit`), `bundle.py` (the
  shared repository bundle).
- `app/api/qa.py` — the 11 REST routes exactly as docs/077 lists them,
  every one gated behind `require_administrator`.
- `app/workers/` — 5 leader-elected background jobs: test run timeout
  sweep, pipeline timeout sweep, flaky test detection
  (edge-triggered), coverage drop sweep (edge-triggered), statistics
  rollup.
- 8 domain events (`app/events/domain_events.py`), 7 notification
  kinds (`app/services/notifications.py`) — 1 fanned from an event
  (`QualityGateFailed` → Quality Gate Failed), 6 called directly.

## Testing

147 tests (52 engine, 19 repository, 27 service, 9 worker, 14 API, 24
deps/notifications, plus 2 smoke tests) at 96.99% coverage, against
real PostgreSQL and Redis. Ruff, Black, and MyPy (scoped to `app/` +
`main.py`) all clean.

**Every `Test*`-prefixed name is aliased at its import statement in
every test module** — see "Ideas that shape everything here" above —
which is what makes it possible to import this service's own models,
enums, services, and workers into pytest at all without triggering a
collection-time error.

Live Docker e2e confirmed: all 5 workers registered on startup;
health/readiness real; the full test-suite listing → test-run start →
quality-gate create/list lifecycle exercised end-to-end through real
HTTP against the running container with real RS256-signed JWTs; **the
test run timeout sweep worker confirmed to autonomously fail a
`RUNNING` test run on its very next scheduled tick after its
`started_at` was backdated via `psql`** — watched directly via `psql`
polling and the worker's own structured logs (`failed: 1` on the tick
immediately after backdating, `failed: 0` on the following tick since
it was already handled), never manually triggered; RBAC confirmed (401
no token, 403 non-admin role, 200 admin); database truncated and
container removed after.
