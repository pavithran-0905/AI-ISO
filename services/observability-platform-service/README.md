# Observability Platform Service

Metrics, logs, traces, events and profiles at platform scale, with
deterministic SLO/error-budget tracking, robust-statistics anomaly
detection, capacity forecasting with honest prediction intervals, root
cause analysis that never claims causation it did not earn, and cost
analytics that keeps unattributed spend visible rather than averaged away.

Implements `docs/064_Enterprise_Observability_Platform_Service.md`.

- **Port** 8035 · **Database** `aiios_observability` · **Redis db** 37

No commercial observability SaaS, no black-box AI scoring — every finding
here can be explained and reproduced from the code that produced it.

---

## The ideas that shape everything here

**A missing number and a zero are different answers, and every engine
names the difference.** An SLI over a window with no traffic is
`NO_DATA`, not `0.0` — reporting zero pages someone at 3am because a
batch job was idle overnight. A capacity forecast with too little history
is `INSUFFICIENT`, not a flat line. A root cause analysis that cannot
separate two candidates reports them tied, not first-and-second. A
correlation computed from silence during a collector outage is refused,
not reported as near-perfect agreement.

**Mean and standard deviation are the wrong tool for infrastructure
metrics.** Every statistical engine here uses robust estimators — median
and MAD for anomaly detection, Theil-Sen alongside OLS for capacity
regression, Spearman rank correlation for root cause — because a single
100x spike should not be able to blind the detector that was supposed to
catch it.

**Every conclusion carries the evidence that produced it.** An anomaly
detection says "6.2 robust deviations above a median of 120ms built from
2016 samples," not "anomaly detected." A capacity forecast reports its
R², its estimator, and the reasons the interval is as wide as it is,
because the same information that produces the answer is what lets
someone disagree with it.

**This engine correlates and traverses dependency graphs. It does not
establish causation.** Root cause candidates carry a discrete evidence
tier and a lexicographic ranking key, never a composite score — a single
number ranks coincidence above mechanism and invites a threshold that
turns a correlation into a causal claim.

---

## What it does

### Signal ingestion

Five signal kinds — metrics, logs, traces, events, profiles — through one
pure validation pipeline (`app/ingestion/pipeline.py`) shared by every
kind: batch-size limits, per-record field checks, clock-skew clamping
(a future timestamp is clamped rather than rejected, since the record may
be legitimate telemetry from a wrong clock), a hard age ceiling (backdating
a signal would silently rewrite a window someone has already reported on),
and deduplication. Every batch returns one outcome per input record, so a
batch of a thousand with three malformed records is neither wholly
accepted nor wholly rejected — a caller can always reconcile what
happened to each one.

Traces are the one signal reconstructed incrementally: a `TraceSession`
row is extended (never overwritten) as spans arrive across batches, and
marked complete only when the specific span with no parent — the root —
is seen, not merely when "some span" arrives without a recorded parent.

### SLO / SLI management (`app/slo/`)

Ratio SLIs (availability, success rate, error rate) computed from counted
good/total windows, with the direction (higher-is-better vs
lower-is-better) carried on the objective so a single comparison never
gets silently inverted for error-rate SLOs. Multi-window burn-rate
alerting (fast + slow, both must exceed their threshold — a short window
alone fires on every blip, a long window alone takes hours to notice a
total outage), with error budgets that may report *negative* remaining
fraction deliberately: clamping an overspent budget to zero hides how far
past it a service is, which is exactly the number that decides whether to
freeze releases.

### Anomaly detection (`app/anomaly/`)

Statistical (robust z-score against a trailing baseline that excludes the
window under test), level-departure (for discrete-valued series like
replica count, where MAD is zero by construction), threshold, and
seasonal (same-phase-of-previous-cycles comparison) detection, merged into
one deduplicated result set. Every detection is classified into a shape
(spike, dip, level shift, seasonal deviation, trend) and a severity band,
with the rationale spelled out in the row itself.

### Capacity forecasting (`app/capacity/`)

OLS and Theil-Sen fit side by side; when they diverge materially, the
robust line is reported and the reason is named. Weekly seasonality is
detected and, when present, removed by fitting on a smoothed series while
still scaling the prediction interval from the raw one (fitting *and*
scaling from the same smoothed series understates the true error by
about √7). A forecast never extrapolates past a hard physical bound, and
exhaustion is found by scanning the emitted trajectory rather than
solving a shortcut formula that would systematically under-warn.

### Root cause analysis (`app/root_cause/`)

Spearman correlation with lag search (searched lags are *counted*, so a
best-of-ten scan is reported as ten tests, not one), Holm-Bonferroni
correction across every comparison made, three-valued clock-aware
precedence (indeterminate is a real answer when two clocks cannot be told
apart), and bounded bidirectional graph traversal for blast radius and
mechanism evidence. Candidates are ranked by tier and lexicographic key,
never a composite score, and two candidates the evidence cannot separate
share a rank and say what evidence would break the tie.

### Service topology (`app/topology/`)

Edges inferred only at instrumented service boundaries — a severed parent
span produces a named "missing link," never a synthesized edge to the
nearest present ancestor. Existence confidence is `1 - Πε^k` over
evidence kinds, capped at three independent observations per hour so a
retry storm cannot manufacture certainty. Single points of failure are
found via dominator analysis (every path from the entry point must pass
through the node), not betweenness, which ranks a busy hub above the
quiet chokepoint that actually takes the estate down.

### Cost analytics (`app/cost/`)

`Decimal` throughout — never `float` — because summing a million usage
rows in a different partition order must produce the same total every
time. Attributed and unattributed cost are kept separate all the way to
the response: an unattributed third of spend is inside the total and
named, never dropped or silently spread. Share bounds are reported as an
interval whose width is exactly the unattributed fraction, so a ranking
narrower than that gap is flagged as unsupported by the data.

### Retention (`app/retention/`)

Raw data is never authorized for deletion ahead of its downsample — a
policy names three tiers (raw, downsampled, coarse) and a caller-supplied
watermark bounds raw deletion regardless of what the clock says. This
build ships no downsampler, so the retention sweep worker executes only
the coarse tier (which has no such dependency); a deployment that adds
downsampling should extend the worker rather than routing raw deletion
through ad hoc logic.

### Search (`app/search/`)

Cursor-based `(occurred_at, id)` pagination everywhere — never offset —
because offset pagination silently skips or repeats rows under the
concurrent-insert load that is highest during exactly the incident a
search is being run for. Every query has a maximum time span; an
unbounded "search all logs" is a full-table scan wearing a search box.

---

## REST API

13 routes under `/observability`, plus `/health`, `/liveness`,
`/readiness`, `/metrics` (Prometheus), `/docs` (OpenAPI). Every route
derives its tenant from the caller's JWT (`organization_id` claim) — never
from a query or body parameter, since accepting one would let a caller
read another tenant's signals by simply naming their organization id.

| Method | Path                        | Purpose                                    |
| ------ | --------------------------- | ------------------------------------------- |
| GET    | `/observability/metrics`    | Samples for one metric series               |
| GET    | `/observability/logs`       | Bounded, cursor-paginated log search        |
| GET    | `/observability/traces`     | One trace's session summary + every span    |
| GET    | `/observability/events`     | Bounded, cursor-paginated event search      |
| GET    | `/observability/topology`   | Nodes and edges for one environment         |
| GET    | `/observability/slos`       | Every enabled SLO                           |
| POST   | `/observability/slos`       | Create an SLO (administrator role required) |
| GET    | `/observability/anomalies`  | Recent anomaly detections                   |
| GET    | `/observability/root-cause` | Root cause reports for one service          |
| GET    | `/observability/capacity`   | Forecasts at risk of exhaustion             |
| GET    | `/observability/cost`       | Cost reports for one period/dimension       |
| GET    | `/observability/statistics` | Rolled-up ingestion/platform statistics     |
| GET    | `/observability/reports`    | Generated reports, newest first             |

## Background workers

Five jobs, all **leader-elected** through `shared_core.scheduler` — each
is pure database work with no per-replica state, so N replicas would be N
times the load for an identical result:

| Worker                     | Default interval | What it does                                          |
| --------------------------- | ----------------- | ------------------------------------------------------ |
| SLO evaluation               | 60s               | Counts good/total spans per SLO, evaluates, persists   |
| Anomaly sweep                 | 300s             | Runs statistical detection over every active series    |
| Topology rebuild               | 600s             | Infers edges from recent spans, upserts the graph       |
| Retention sweep                 | 3600s            | Applies the coarse-tier retention cutoff                |
| Statistics rollup                 | 900s           | Idempotent per-window ingestion/error rollup            |

## Configuration

Every analytical threshold is a configuration field
(`app/config/settings.py`), never a compiled-in constant — an anomaly
detector whose sensitivity cannot be adjusted per deployment gets turned
off wholesale the first time it is too noisy for one particular metric.

Key environment variables (prefix `AIIOS_OBSERVABILITY_PLATFORM_SERVICE_`
for service-specific fields; shared infrastructure fields use the
platform-wide `AIIOS_DATABASE_*` / `AIIOS_REDIS_*` / `AIIOS_RABBITMQ_*`
prefixes):

- `PORT` (default `8035`), `JWT_PUBLIC_KEY_PATH`
- `MAX_BATCH_SIZE`, `MAX_LABEL_COUNT`, `CLOCK_SKEW_TOLERANCE_SECONDS`
- `ANOMALY_ROBUST_Z_THRESHOLD`, `ANOMALY_MIN_HISTORY_POINTS`
- `FORECAST_MIN_R_SQUARED`, `FORECAST_DEFAULT_HORIZON_DAYS`
- `FAST_BURN_THRESHOLD`, `SLOW_BURN_THRESHOLD`, `SLO_AT_RISK_BUDGET_FRACTION`
- `WORKERS_ENABLED` plus a `*_SECONDS` interval per worker

## Running locally

```bash
cd services/observability-platform-service
uv sync
uv run alembic upgrade head
uv run uvicorn main:app --host 0.0.0.0 --port 8035
```

Requires PostgreSQL (database `aiios_observability`), Redis, and
RabbitMQ reachable per the `AIIOS_*` environment variables. **Every AI-IOS
service shares one Postgres instance but owns its own database and its
own Alembic version table** (`alembic_version_observability_platform_service`)
— the default single `alembic_version` table cannot track more than one
service's migration chain at a time, since every service connects to the
same physical database.

## Testing

```bash
uv run python -m pytest tests/ --cov=app --cov-report=term-missing
```

658 tests, 97% coverage. Every test that touches persistence runs against
a **real** PostgreSQL and Redis — nothing here mocks infrastructure. Each
test gets its own SAVEPOINT-isolated database transaction (rolled back at
teardown) and its own tenant (`organization_id`), so every test is
incidentally also a tenant-isolation test. Notification tests run against
the real `shared_core` notification framework rather than a mock, which is
what surfaces defects a mock publisher would hide by construction (e.g. a
notification body referencing a field the event payload never populated).

Background workers are tested by calling `tick()` directly against a real
session factory — never by mocking the scheduler — since leader election
and distributed locking are `shared_core.scheduler`'s concern, not this
service's.

Quality gates: `ruff check .`, `black --check .`, and
`mypy app/ main.py` (matching this project's CI convention of gating
`app/` and `main.py`, not `tests/`).
