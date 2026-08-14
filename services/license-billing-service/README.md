# License & Billing Service

Licensing, subscriptions, feature entitlements, usage metering, billing,
invoicing, payments, quotas, revenue analytics, and commercial lifecycle
management across SaaS, hybrid, self-hosted, MSP, OEM, and enterprise
licensing models.

Implements `docs/069_Enterprise_License_Billing_Service.md`.

- **Port** 8040 · **Database** `aiios_billing` · **Redis db** 42

This service is the system of record for licensing and billing
decisions, not a payment gateway, tax authority, ERP, or accounting
system — see *Scope boundary* below for exactly where it stops.

---

## The ideas that shape everything here

**A license or subscription only moves between adjacent, explicitly
allowed lifecycle states.** Skipping straight from `ISSUED` to `ACTIVE`
without activation would treat a license nobody has actually activated
as in use; jumping a subscription from `TRIAL` to `SUSPENDED` would
suspend something that was never billed in the first place. Every hop
in both state machines (`app/licenses/engine.py`,
`app/subscriptions/engine.py`) exists because something real has to
happen at that step — `REVOKED`/`CANCELLED` are the only truly terminal
states; `EXPIRED` can still be reactivated by a late renewal.

**A domain field must never reuse one of `BaseEntityMixin`'s reserved
column names** (`id`, `created_at`, `updated_at`, `is_active`,
`organization_id`, `project_id`, `version`). Every "currently usable"
flag this service needed — `LicenseKey.is_enabled`,
`LicenseActivation.is_enabled`, `LicenseEntitlement.is_enabled`,
`SubscriptionFeature.is_enabled`, `SubscriptionPlan.is_enabled`,
`Discount.is_enabled` — is named `is_enabled`, deliberately never
`is_active`, since `is_active` is already `BaseEntityMixin`'s own
soft-delete flag that every repository's `_base_select()` filters on.
Checked proactively from the first model draft, learned the hard way by
`services/edge-management-service` in Prompt 067 (see its own README
and `AI_MEMORY.md` for the collision that lesson came from).

**Enum-typed columns are plain `String`, not a SQL `Enum` type — every
comparison against a possibly-ORM-sourced value uses `==`, never `is`.**
Applied proactively in every engine from the first draft, per
`services/multi-cluster-management-service`'s own hard-won lesson.

**`None` always means unlimited, never "zero."** A seat limit, a
feature limit, or a quota burst allowance that was never set is not the
same fact as one capped at zero — the former grants unrestricted use,
the latter blocks it entirely. `app/entitlements/engine.py` and
`app/licenses/engine.py`'s seat check both hold this distinction
explicit rather than collapsing it into a single integer.

**A refused hard quota never increments usage; a soft quota never
refuses.** `app/quotas/engine.py` keeps that distinction explicit
because the two limit kinds docs/069 names exist precisely so a caller
can choose "warn but allow" versus "actually enforce."

**An invoice total is the sum of its line items, discounted, never
independently entered.** `app/billing/engine.py` only ever derives a
total from its own line items — a total that could disagree with them
is a total nobody can trust.

**Payments and license activation are reported, never processed.** See
*Scope boundary*.

---

## What it does

### Customers (`app/models/customers.py`, `app/services/customers.py`)

The billed business entity — organization, department, business unit,
reseller, partner, MSP, or OEM — nested via `parent_customer_id` so an
end customer under an MSP/reseller is represented without flattening
the relationship. Publishes `CustomerCreated`.

### Licenses (`app/licenses/`, `app/services/licenses.py`)

Issuance, seat activation/deactivation bounded by `seat_limit`
(`None` = unlimited, a floating/site license), revocation, and feature
entitlement grants (`app/entitlements/`) — across
SaaS/perpetual/term/evaluation/trial/enterprise/site/OEM/academic/MSP/
consumption/BYOL/offline/floating/named-user license models. Offline
license files (`app/offline/`) are validated against their own
recorded SHA-256 hash, never trusted because they merely parse.

### Subscriptions (`app/subscriptions/`, `app/services/subscriptions.py`)

Plan catalog, feature entitlements, and subscription lifecycle —
trial → active ⇄ suspended/pending-renewal → cancelled/expired, with
renewal recomputing the billing period and reactivation from `EXPIRED`
possible on a late payment.

### Usage & quotas (`app/usage/`, `app/quotas/`, `app/services/usage.py`, `app/services/quotas.py`)

Immutable usage-event recording with idempotent per-window rollup
(`UsageCounter`), and quota admission control classifying every request
ok/warning/exceeded against a configurable warning threshold, with hard
quotas enforcing an optional burst allowance and soft quotas only ever
warning.

### Billing (`app/billing/`, `app/pricing/`, `app/payments/`, `app/services/invoices.py`, `app/services/billing_accounts.py`, `app/services/payments.py`)

Billing accounts, payment methods (a tokenized/masked reference, never
a real instrument), invoice generation from line items with
percentage/fixed discounts and tiered pricing, payment transaction
recording with configurable-ceiling retry eligibility, discounts, and
promotion redemption validated against its own start/end window and
redemption limit.

### Contracts (`app/models/contracts.py`, `app/services/contracts.py`)

Enterprise contract creation through an approval workflow — draft →
approved/rejected, with termination as the exit.

### Marketplace (`app/services/marketplace.py`)

Third-party marketplace subscription purchases, publishing
`MarketplacePurchaseCompleted`.

### Analytics & reporting (`app/analytics/`, `app/services/statistics.py`, `app/services/reports.py`)

MRR/ARR normalization across every billing model (usage-based models
contribute `0.0` to MRR — their revenue is counted through actual
billed usage, never estimated), churn/success rates that are `None` on
a zero denominator rather than a misleading `0%`/`100%`, idempotent
per-window statistics rollup, and revenue/usage/subscription/invoice/
renewal/quota/license/audit report generation.

### Audit (`app/services/audit.py`)

The one write path onto the immutable `billing_audit` trail — every
other service calls through here rather than constructing rows
directly, so license creation/activation, subscription changes, billing
changes, invoice generation, payment events, and contract changes
cannot quietly stop being recorded through a second, slightly different
construction path.

---

## Scope boundary

Per docs/069's own "DO NOT IMPLEMENT" section, this service does **not**
integrate a real payment gateway SDK, a tax authority, an ERP system, or
accounting software. Consistent with that boundary, several spec
sections are implemented as real, tested decision logic with **no live
external system wired up**, matching the "declared seam" pattern
`services/backup-dr-service` established in Prompt 065 and every
service since:

- **Payments** (`app/services/payments.py`): retry eligibility and
  transaction state are real and tested; `PaymentCreateRequest.succeeded`
  is reported by the caller (a payment gateway webhook handler, an
  operator) — this service never processes a real payment itself.
- **Payment methods** (`app/models/billing.py`):
  `PaymentMethod.reference` is a tokenized/masked lookup key, never a
  real card or bank account number — that is a payment gateway's job.
- **Tax/ERP/accounting**: invoice totals and revenue analytics are real
  and tested; there is no live tax-authority rate lookup, ERP posting,
  or accounting-software export.
- **Offline licensing**: file hash validation is real; there is no live
  code-signing infrastructure generating the files themselves.

---

## REST API

17 routes, plus `/health`, `/liveness`, `/readiness`, `/metrics`
(Prometheus), `/docs` (OpenAPI). Every route derives its tenant from
the caller's JWT (`organization_id` claim) — never from a query or body
parameter.

| Method | Path                          | Purpose                                                              |
| ------ | ------------------------------ | ------------------------------------------------------------------- |
| GET    | `/licenses`                    | List licenses                                                        |
| POST   | `/licenses`                    | Issue a license (administrator role required)                        |
| GET    | `/licenses/{id}`                 | Get a license                                                        |
| POST   | `/licenses/{id}/activate`          | Activate a license seat (`409` past the seat limit)                    |
| POST   | `/licenses/{id}/revoke`              | Revoke a license (administrator role required; `409` if refused)         |
| GET    | `/subscriptions`                       | List subscriptions                                                       |
| POST   | `/subscriptions`                         | Create a subscription (administrator role required)                       |
| PUT    | `/subscriptions/{id}`                      | Advance a subscription's lifecycle (administrator role required; `409` if refused) |
| DELETE | `/subscriptions/{id}`                        | Cancel a subscription (administrator role required; `409` if refused)        |
| GET    | `/billing/invoices`                            | List invoices                                                                  |
| POST   | `/billing/invoices`                              | Generate an invoice (administrator role required)                               |
| GET    | `/billing/payments`                                | List payment transactions                                                        |
| POST   | `/billing/payments`                                  | Record a payment attempt (administrator role required)                            |
| GET    | `/billing/usage`                                       | Usage counters for a customer                                                       |
| GET    | `/billing/quotas`                                        | Quotas (all, or for a customer)                                                       |
| GET    | `/billing/statistics`                                      | Rolled-up revenue/billing statistics                                                    |
| GET    | `/billing/reports`                                           | Generated reports, newest first                                                           |

## Background workers

Five jobs, all **leader-elected** through `shared_core.scheduler` — each
is pure database work with no per-replica state:

| Worker                     | Default interval | What it does                                                              |
| --------------------------- | ----------------- | ---------------------------------------------------------------------------- |
| Subscription renewal sweep      | 3600s         | Notifies for upcoming renewals/trial expiry; expires subscriptions past their grace period |
| License expiry sweep                | 3600s     | Expires licenses past `expires_at` and notifies                                  |
| Quota reset sweep                       | 900s  | Opens the current calendar period's usage window for every quota ahead of first use |
| Invoice generation sweep                   | 3600s | Issues one invoice per billing period per active subscription; marks overdue invoices |
| Statistics rollup                             | 900s | Idempotent per-window MRR/ARR/churn/payments/quota rollup                          |

## Configuration

Every commercial threshold is a configuration field
(`app/config/settings.py`), never a compiled-in constant — a grace
period, a quota burst allowance, or an invoice due window a deployment
needs to tune to its own commercial terms without a release.

Key environment variables (prefix `AIIOS_LICENSE_BILLING_SERVICE_` for
service-specific fields; shared infrastructure fields use the
platform-wide `AIIOS_DATABASE_*` / `AIIOS_REDIS_*` / `AIIOS_RABBITMQ_*`
prefixes):

- `PORT` (default `8040`), `JWT_PUBLIC_KEY_PATH`
- `SUBSCRIPTION_GRACE_PERIOD_DAYS`, `RENEWAL_REMINDER_DAYS_BEFORE`, `TRIAL_EXPIRING_REMINDER_DAYS_BEFORE`
- `LICENSE_EXPIRING_REMINDER_DAYS_BEFORE`, `OFFLINE_LICENSE_MAX_VALIDITY_DAYS`
- `QUOTA_ALERT_WARNING_FRACTION`, `QUOTA_BURST_GRACE_FRACTION`
- `INVOICE_DUE_DAYS`, `PAYMENT_RETRY_MAX_ATTEMPTS`
- `WORKERS_ENABLED` plus a `*_SECONDS` interval per worker

## Running locally

```bash
cd services/license-billing-service
uv sync
uv run alembic upgrade head
uv run uvicorn main:app --host 0.0.0.0 --port 8040
```

Requires PostgreSQL (database `aiios_billing`), Redis, and RabbitMQ
reachable per the `AIIOS_*` environment variables. **Every AI-IOS
service shares one Postgres instance but owns its own database and its
own Alembic version table** (`alembic_version_license_billing_service`).

## Testing

```bash
uv run python -m pytest tests/ --cov=app --cov-report=term-missing
```

264 tests, 96.5% coverage. Every test that touches persistence runs
against a **real** PostgreSQL and Redis. Each test gets its own
SAVEPOINT-isolated database transaction (rolled back at teardown) and
its own tenant (`organization_id`).

Background workers are tested by calling `tick()` directly against a
real session factory bound to the test's own connection, using real
wall-clock time throughout. Live Docker e2e additionally confirmed all
five workers register and acquire scheduler leadership on startup, and
the statistics rollup worker fires autonomously on its own schedule —
never manually triggered — writing a real `billing_statistics` row
observed directly in the database.

Quality gates: `ruff check .`, `black --check .`, and
`mypy app/ main.py` (matching this project's CI convention of gating
`app/` and `main.py`, not `tests/`).
