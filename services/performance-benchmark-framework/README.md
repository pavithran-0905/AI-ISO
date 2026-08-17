# Performance & Benchmark Framework

Enterprise Performance & Benchmark Framework Service (Prompt 078) —
benchmarking, profiling, capacity planning, scalability validation,
regression detection, SLO verification, and AI-assisted optimization
across the AI-IOS platform.

Port `8049`. Database `aiios_performance_benchmark_framework`. Redis db `51`.

## Ideas that shape everything here

**A control plane over benchmark and performance activity, not a load
generator.** docs/078's own "DO NOT IMPLEMENT" list excludes
third-party benchmarking SaaS, OS profilers, hardware drivers, and
cloud provider benchmark services. Every engine and service here
models and evaluates *records* of benchmark runs, performance metrics,
capacity forecasts, and SLO results that some external system (a load
tool, an APM agent, a monitoring pipeline) reports in — it never
generates load or profiles a process itself.

**A shared, event-free job engine.** `app.benchmark.engine`
(`BenchmarkRunStatus` PENDING→RUNNING→{SUCCEEDED,FAILED},
`validate_transition`, `is_job_stuck`) is the same proven shape
`services/testing-quality-framework`'s own `app.pipeline.engine`
(Prompt 077) and `services/upgrade-framework-service`'s shared job
engine (Prompt 076) established — pure status transitions with no
events of its own. `BenchmarkRunService` layers `BenchmarkStarted`/
`BenchmarkCompleted` on top; unlike Prompt 077's `TestRunService`,
docs/078 names only one completion event (not a Started/Completed/
Failed triple), so `BenchmarkCompleted` fires on every terminal state
regardless of outcome.

**One event chain links regression detection all the way to an
optimization recommendation.** `RegressionSweepWorker` doesn't stop at
recording a `performance_regressions` row: on every detected
regression it also calls `OptimizationRecommendationService.create()`,
mapping the regression's own kind to a recommendation category
(`app.optimization.engine.category_for_regression` — database
regressions suggest query optimization, workflow regressions suggest
workflow optimization, everything else defaults to infrastructure).
`CapacityThresholdSweepWorker` does the same for breached forecasts,
always with the `SCALING` category. This is how docs/078's own "AI
OPTIMIZATION" section (a declared integration seam over Prompt 060)
is implemented without inventing a fictional external AI call: the
recommendation is a direct, traceable consequence of a measured fact
this service already holds.

**A self-contained `SemanticVersion`-free regression classifier.**
Unlike `services/testing-quality-framework`'s contract-compatibility
engine, this service's own `app.regression.engine` doesn't need
version comparison — it classifies severity purely from how far a
metric's magnitude drifted past its own configured warning/critical
thresholds (`classify_severity`, scaled proportionally against the
critical threshold into LOW/MEDIUM/HIGH/CRITICAL bands), and infers
*which kind* of regression occurred from the metric's own name first,
falling back to the benchmark suite's own domain
(`infer_regression_type`).

**Automatic Baseline Selection, not a manual admin step.** docs/078's
own BASELINES section lists this as a required capability, and there
is no `POST` route for baselines at all: `BenchmarkResultService.record()`
calls `BenchmarkBaselineService.get_or_create_initial()` on every
recorded result, which creates a baseline from a metric's own
first-ever value if none exists yet, or returns the existing one
unchanged otherwise. The regression sweep worker then compares every
later result against whatever baseline was auto-selected.

**One fanned notification, six direct.** `RegressionDetected` is the
only one of docs/078's seven notification kinds wired through
`NotifyingPublisher` (into Performance Regression) — the same "1
fanned, N direct" shape every AI-IOS service in this build uses. The
other six are called directly by the code that observes the underlying
fact: Capacity Warning and SLO Violation by their own edge-triggered
sweep workers, Benchmark Completed by `BenchmarkRunService` on every
terminal state, Optimization Available / Scaling Recommendation by
`OptimizationRecommendationService` (chosen by category), and
Infrastructure Bottleneck synchronously by `ResourceUtilizationService`
the moment a recorded sample is itself at bottleneck level — this
process cannot probe live resource utilization beyond what a caller
reports, the same caller-reported-outcome shape
`services/testing-quality-framework`'s own `SecurityService` uses.

**Every route requires an administrator role.** Benchmark execution,
capacity planning, and optimization recommendations are internal
engineering signals, not customer-facing data — the same
administrator-heavy routing every adjacent infrastructure-framework
service in this build (075, 076, 077) established.

**Nearly every REST route is read-only by design.** Of the 11 routes
docs/078 lists, only `POST /benchmarks` (define a suite) and
`POST /benchmarks/run` (start a run) mutate anything; performance
metrics, regressions, capacity forecasts, optimization recommendations,
and SLO results are all populated internally by the five workers (or,
in tests, the services directly) and only ever listed over HTTP — the
same "no route for tables workers own" precedent
`services/upgrade-framework-service` set for migration history
(Prompt 076).

## Architecture

- `app/models/` — 18 tables across 11 files: `benchmark_definitions.py`
  (BenchmarkSuite, BenchmarkProfile), `benchmark_execution.py`
  (BenchmarkRun, BenchmarkResult), `baselines.py` (BenchmarkBaseline),
  `performance.py` (PerformanceProfile, PerformanceMetric),
  `capacity.py` (CapacityModel, CapacityForecast), `optimization.py`
  (OptimizationRecommendation), `regressions.py`
  (PerformanceRegression), `utilization.py` (ResourceUtilization),
  `statistics_tables.py` (LatencyStatistics, ThroughputStatistics),
  `slo.py` (SloResult), `reporting.py` (BenchmarkStatistic,
  BenchmarkReport, BenchmarkAudit).
- 10 pure engines, each hand-verified before any pytest was written
  (64 checks, zero engine defects — one hand-verification-script bug,
  a floating-point exact-equality check, found and fixed instead):
  `app/benchmark/engine.py` (the shared job lifecycle),
  `app/regression/engine.py` (magnitude, severity, and type
  classification), `app/slo/engine.py` (direction-aware compliance),
  `app/capacity/engine.py` (compound-growth forecasting),
  `app/optimization/engine.py` (impact scoring, regression→category
  mapping), `app/latency/engine.py` (percentile computation),
  `app/throughput/engine.py` (rate and drop detection),
  `app/utilization/engine.py` (bottleneck classification),
  `app/baseline/engine.py` (median-based baseline selection, staleness
  detection), `app/analytics/engine.py` (success/compliance/
  regression-free rate, equal-weighted performance score).
- `app/services/` — one service per table-group plus
  `notifications.py` (`BenchmarkNotifier` + `NotifyingPublisher`),
  `audit.py` (the single write path for `benchmark_audit`),
  `bundle.py` (the shared repository bundle).
- `app/api/benchmark.py` — the 11 REST routes exactly as docs/078
  lists them, every one gated behind `require_administrator`.
- `app/workers/` — 5 leader-elected background jobs: benchmark run
  timeout sweep, regression sweep (edge-triggered, also generates
  optimization recommendations), SLO compliance sweep
  (edge-triggered), capacity threshold sweep (edge-triggered, also
  generates scaling recommendations), statistics rollup.
- 8 domain events (`app/events/domain_events.py`), 7 notification
  kinds (`app/services/notifications.py`) — 1 fanned from an event
  (`RegressionDetected` → Performance Regression), 6 called directly.

## Testing

160 tests (70 engine, 20 repository, 21 service, 11 worker, 12 API, 25
deps/notifications, plus 2 smoke tests) at 96.68% coverage, against
real PostgreSQL and Redis. Ruff, Black, and MyPy (scoped to `app/` +
`main.py`) all clean.

A genuine bug was caught by the worker test suite before Docker e2e:
`CapacityThresholdSweepWorker`'s own `tick()` created an optimization
recommendation row but never called `session.commit()`, so the write
was silently rolled back at the end of every tick. The test asserting
the recommendation existed in a fresh session (not the one that wrote
it) failed immediately, confirming exactly why worker tests re-read
through a separate session rather than trusting the same one that
performed the write.

Live Docker e2e confirmed: all 5 workers registered on startup;
health/readiness real; a benchmark suite created and a run started
through real HTTP with real RS256-signed JWTs; **the benchmark run
timeout sweep worker confirmed to autonomously fail a `RUNNING` run on
its very next scheduled tick after `started_at` was backdated via
`psql`**, and, on the very next tick after that, **the regression
sweep worker autonomously detected an 80% latency regression against
a seeded baseline, recorded a `CRITICAL`-severity `performance_regressions`
row, published `RegressionDetected`, and generated a matching
`infrastructure`-category optimization recommendation** — all watched
directly via the container's own structured audit logs, never manually
triggered; RBAC confirmed (401 no token, 403 non-admin role, 200
admin); database truncated and container removed after.
