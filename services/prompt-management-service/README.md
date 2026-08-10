# AI-IOS Enterprise Prompt Management Service

Prompt 061. The centralized registry every AI-generated interaction in
AI-IOS retrieves its prompts from, instead of embedding them in
application code: semantic versioning, sandboxed templating, variable
resolution, testing, evaluation, A/B experiments, optimization
suggestions, security scanning, approval governance, analytics, and an
immutable audit trail.

Runs on port **8032** against database **`aiios_prompt_management`**
and Redis **db 34**.

---

## What this service is

**A prompt is an identity; its text lives only in immutable versions.**
That split is the spine of the whole service, and it is what makes the
governance real rather than nominal:

- **Versioning** — every edit is a new `PromptVersion` row.
- **Approval** — a gate is attached to a *revision*, not a prompt.
- **Rollback** — moves a pointer; it never restores or rewrites text,
  so "this is the wording that was approved" stays true a year later.
- **Comparison** — two revisions can be diffed because both still
  exist verbatim.

Scaled up from the same `AiPrompt`/`AiPromptVersion` pair
`ai-assistant-service` established in Prompt 046.

### This service never calls a model

It governs prompts; it does not execute them. There is no provider
credential anywhere in this codebase, and that constraint shapes real
design decisions rather than being an omission:

- Evaluation scorers are **deterministic and model-free**. An
  LLM-as-judge would need a credential and would also score the same
  prompt differently on two runs — exactly wrong for a metric gating a
  publish or picking an A/B winner.
- Prompt tests assert on the **rendered prompt**, not a model reply. A
  caller that already holds a reply may pass it as `actual_output`.
- `prompt_executions` rows are reported back **after the fact** by
  whichever service ran the prompt (ai-assistant-service,
  ai-agent-platform-service).

### Reused frameworks vs genuine gaps

Established by a research pass before any code was written:

- **Reused directly:** Jinja2's `SandboxedEnvironment` (the same call
  `shared_core.notifications.renderer` and `ai-assistant-service` each
  made, for the same reason); `shared_core.plugins.versioning` for
  semver comparison — the same reuse Prompts 058/059 made;
  `shared_core.workflow.expressions`' vetted sandboxed evaluator for
  computed variables; `shared_core.scheduler` (all four workers);
  `shared_core.events`; `shared_core.telemetry`; `shared_core.cache`.
- **Genuine gaps, built new:** A/B statistical significance — confirmed
  by a repo-wide search that *nothing* in this monorepo does hypothesis
  testing ([`app/abtesting/statistics.py`](app/abtesting/statistics.py));
  prompt optimization ([`app/optimization/`](app/optimization/));
  token estimation — no `tiktoken`, no `count_tokens` anywhere
  ([`app/optimization/tokens.py`](app/optimization/tokens.py));
  version *bumping*, since `shared_core` compares versions but never
  derives one ([`app/versioning/semver.py`](app/versioning/semver.py));
  prompt-shaped security scanning
  ([`app/security/scanner.py`](app/security/scanner.py)).

---

## Three properties worth understanding before changing anything

### The sandbox is not optional

A prompt template is user-authored *by definition* — that is the entire
point of this service. Unrestricted Jinja2 reaches arbitrary Python
attributes through any object in its context, so an ordinary
`Environment` over a user-editable template is a real code-execution
path. `render_body` is verified against four classic SSTI payloads
(`''.__class__.__mro__[1].__subclasses__()`,
`config.__class__.__init__.__globals__`,
`cycler.__init__.__globals__.os.popen()`, `''.__class__.__base__`) —
all blocked.

`StrictUndefined` is equally deliberate: a prompt that silently renders
half its instructions because a variable was absent is far worse than
one that fails loudly. The model still answers, the answer looks
plausible, and nothing says the instructions were truncated.

### Returned ≠ recorded

`RenderedResult.body` carries the resolved secret — it has to, to be
useful. `RenderedResult.masked_body` carries `[REDACTED]`, and that is
what goes into `prompt_executions.rendered_prompt`. The API returns
only the former, because offering both would invite a caller to log the
wrong one. `POST /prompts/executions` masks server-side rather than
trusting the caller, since this service is the one that knows which
variables are sensitive.

Security findings likewise record the finding *kind* and severity,
never the matched text — a scan row quoting the secret it found would
put that secret in the database, in every backup, and in any log line
rendering the row.

### Nothing here rewrites an approved prompt

Optimization returns **suggestions**, never mutations. Accepting one
goes through `PromptService.add_version`, so it lands in the same
review-and-approval path as a hand-written edit. `INSTRUCTION_REFINEMENT`,
`FEW_SHOT`, and `CHAIN` are reported as *advisory findings* with no
proposed rewrite: this service cannot call a model to check that a
rewrite preserved meaning, and a rewrite that changes meaning is worse
than no suggestion at all.

The A/B sweep marks a winner `PROMOTED` but does not publish, for the
same reason — promoting means publishing a new version, which is
exactly what the approval workflow exists to gate.

---

## Layout

| Path | What lives there |
| --- | --- |
| [`app/models/`](app/models/) | 17 tables |
| [`app/templating/`](app/templating/) | Sandboxed renderer with a bounded, DB-backed loader |
| [`app/variables/`](app/variables/) | Eight-source resolution, precedence, validation, masking |
| [`app/versioning/`](app/versioning/) | Semver bumping, diffing, ordering |
| [`app/security/`](app/security/) | Redaction patterns + the prompt security scanner |
| [`app/evaluation/`](app/evaluation/) | Nine deterministic scorers |
| [`app/optimization/`](app/optimization/) | Token estimator + suggestion engine |
| [`app/abtesting/`](app/abtesting/) | Two-proportion z-test, stdlib only |
| [`app/repositories/`](app/repositories/) | 17 repositories, `require_in_org` named apart from the base's unscoped `require_by_id` |
| [`app/services/`](app/services/) | Lifecycle, governance, rendering, testing/A-B, analytics |
| [`app/api/`](app/api/) | 34 routes — the 13 literal docs/061 endpoints plus health |
| [`app/workers/`](app/workers/) | Approval expiry, review cycle, A/B evaluation, statistics rollup — all leader-elected |

### The router-registration order matters

[`app/api/prompts.py`](app/api/prompts.py) registers every
static-segment route (`/test`, `/evaluate`, `/optimize`, `/ab-test`,
`/statistics`, `/reports`, `/executions`, `/reviews`, `/approvals`)
*before* the `GET/PUT/DELETE /{prompt_id}` catch-all. Declared the
other way round, `POST /prompts/test` would be hijacked as
`prompt_id="test"` and fail UUID parsing before reaching its handler —
the same bug class already found and fixed in
notification-center-service, plugin-marketplace-service, and
ai-agent-platform-service. Guarded by construction and by an explicit
regression test.

---

## Running it

```bash
docker build -t aiios/prompt-management-service:0.1.0 \
  -f services/prompt-management-service/Dockerfile .

MSYS_NO_PATHCONV=1 docker run -d --name aiios_prompt_management \
  --network aiios_aiios_network -p 8032:8032 \
  -e AIIOS_DATABASE_HOST=aiios_postgres -e AIIOS_DATABASE_PORT=5432 \
  -e AIIOS_DATABASE_NAME=aiios_prompt_management \
  -e AIIOS_DATABASE_USER=aiios -e AIIOS_DATABASE_PASSWORD=change-me \
  -e AIIOS_REDIS_HOST=aiios_redis -e AIIOS_REDIS_DB=34 \
  -e AIIOS_REDIS_PASSWORD=change-me \
  -e AIIOS_RABBITMQ_HOST=aiios_rabbitmq -e AIIOS_RABBITMQ_USER=aiios \
  -e AIIOS_RABBITMQ_PASSWORD=change-me -e AIIOS_RABBITMQ_VHOST=/aiios \
  aiios/prompt-management-service:0.1.0
```

Migrations: `uv run alembic upgrade head`. `keys/jwt_public_key.pem` is
the public half of `services/authentication-service`'s signing key —
this service verifies tokens but never issues them.

**`MSYS_NO_PATHCONV=1` is required on any `docker run` whose arguments
contain a leading `/`** (here, `AIIOS_RABBITMQ_VHOST=/aiios`). Git Bash
on Windows otherwise rewrites it into a Windows path before Docker sees
it, producing an opaque `AMQPInternalError` with no hint the vhost was
mangled.

---

## Tests

Real PostgreSQL, Redis, and RabbitMQ throughout. Nothing here mocks
infrastructure.

```bash
uv run python -m pytest -q --cov=app --cov-report=term-missing
```

Unlike `ai-assistant-service` or `ai-agent-platform-service`, this
suite carries no "the LLM may be unreachable" caveat — this service
calls no model provider, so every operation is deterministic and every
test asserts exact outcomes.

**1122 tests, 100.00% branch coverage on `app`.** Ruff, Black, and MyPy
all clean.

Two things the suite deliberately checks structurally rather than
behaviourally, because a route added later would not fail any
behavioural test:

- **Every one of the 30 routes requires authentication.** Asserted by
  walking the router's own AST for a `CurrentUserId` annotation. The
  read routes matter most: `GET /prompts/{id}/versions` returns full
  prompt bodies, so an open read would let anyone who can reach the port
  enumerate every organization's prompts by varying one query parameter.
- **Every worker really registers *and* gets a `next_run`.** One test
  enables workers for real and drives the actual lifespan against real
  RabbitMQ and Redis. Without it `_build_workers` never executed in any
  test, and a scheduler that silently failed to register would look
  exactly like a healthy service until someone noticed approvals never
  expiring.

### Tool shims are blocked on this machine

Windows Application Control intermittently blocks `uv`'s generated
`.exe` shims. Invoke tools as modules instead — `uv run python -m black`,
`uv run python -m pytest`. MyPy has a second problem (its compiled
`__mypyc` extension is blocked even as a module) and must run inside
the container.

---

## Notes worth keeping

- **`add_version` bumps from the HIGHEST version, not the live one.**
  After a rollback those differ (live `1.0.0`, highest `1.1.0`), and
  bumping from the live pointer would emit `1.0.1` while `1.1.0`
  already exists.
- **Variable declarations carry forward as independent copies.**
  Variables are per-revision so approving one version is not changed by
  a later one adding a variable — but without the copy-forward, a
  one-word wording tweak would render fine as a draft and then fail
  with `'name' is undefined` the moment it went live.
- **`is_valid` checks the same parser `bump` uses.** `shared_core`'s
  `parse_version` accepts a two-part `"1.2"` that everything here
  rejects; a validator disagreeing with what it validates for is worse
  than none.
- **PostgreSQL's `::` cast collides with SQLAlchemy's `:name` binds.**
  Use `CAST(:x AS integer)`.
- **`declared_variables` guards the compile, not just the parse.**
  Jinja2's `meta.find_undeclared_variables` runs the code generator,
  which raises `TemplateAssertionError` for an unknown filter — a
  failure mode the parser accepts.
- **Enum columns are plain `str` at runtime.** Compare with `==`, never
  `is`.
- **JSON list columns are reassigned, never mutated in place.**
- **`start_span` takes `**attributes`, not an `attributes=` keyword.**
  Passing one silently drops every attribute — a confirmed repo-wide
  defect in services built before Prompt 054.
- **A mandatory review is resolved per reviewer, on their LATEST
  verdict.** Only `APPROVED` resolves; `REJECTED` blocks like
  `CHANGES_REQUESTED` does. `ReviewService.request` refuses only a second
  *pending* request, so re-review after a changes-requested verdict is a
  supported flow — and counting every mandatory row instead would leave
  the superseded objection blocking forever, with the only escape being
  a byte-identical revision cut purely to reset review state.
- **`PromptVersion.authored_by`, not `created_by`.** `created_by` belongs
  to `AuditMixin`, which docs/018 says no entity may redefine and which
  types it as a `UUID`. Shadowing it with a `String` leaves two writers
  on one column with different value shapes. An actor here is not always
  a user — a revision can be authored by a sweep.
- **`PromptRepository.search_in_org`, not `search`.** The base's own
  `search` takes an explicit field list and no tenant, so overloading the
  name both breaks substitutability and makes an unscoped platform-wide
  search look identical to a tenant-scoped one at the call site — the
  same reason `require_in_org` is named apart from `require_by_id`.

---

## What's deliberately out of scope

- **LLM fine-tuning and model training**, per docs/061's own
  DO-NOT-IMPLEMENT list.
- **Business-specific prompts and customer prompt libraries** — this
  service is the registry, not its contents.
- **Multiple-comparison correction and sequential testing** in the A/B
  engine. Both matter in a mature experimentation platform and both are
  wrong to fake; the engine instead refuses to call significance before
  both arms reach their sample horizon, which is the defence that
  actually matters against false positives.
- **Live secret resolution over HTTP.** `POST /prompts/{id}/render`
  returns the placeholder for secret references. Resolving them needs
  the caller's own authority against secrets-management-service, which
  is a deliberate follow-up rather than something to do implicitly on
  every render.
- **A real OpenTelemetry `TracerProvider` in the app factory.** A
  repo-wide grep confirmed no AI-IOS service wires one yet; this
  service follows that precedent rather than diverging alone.
