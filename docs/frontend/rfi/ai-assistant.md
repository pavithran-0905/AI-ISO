# AI Assistant

Per Prompt 010 §55, this honestly separates **IMPLEMENTED** from
**PLANNED**/**UNAVAILABLE** for the Enterprise AI Assistant &
Intelligence Experience. Nothing here claims future functionality as
currently available. See `../rfi/README.md` and the prior per-feature
RFI docs (`dashboard.md`, `monitoring.md`, `alerting.md`,
`reporting.md`, `automation.md`) for the foundation this builds on.

## Conversational assistant — IMPLEMENTED

A real two-panel workspace (conversation list + transcript/composer)
against `POST /ai/chat` and its supporting `GET /ai/conversations`
family — 26 of 37 real `ai-assistant-service` routes consumed across 5
sub-modules (chat, knowledge, insights, catalog, prompts). See
`../developer-guide/ai-assistant.md` for the full endpoint inventory
and why each unconsumed route was left out.

## Token-level streaming — UNAVAILABLE (documented, not implemented)

§10 asks that streaming not be faked. `POST /ai/chat/stream` exists
and is a real SSE endpoint, but its own module docstring admits the
underlying provider call is awaited to completion before the answer is
chopped into fixed-size chunks and dripped out — zero
time-to-first-token improvement over the synchronous endpoint. Rather
than build a cosmetic typewriter effect that implies real incremental
generation, this feature consumes only `POST /ai/chat` with a single
"sending" loading state.

## Permission-aware tool use — IMPLEMENTED (mechanism, not a security boundary)

`allow_mutating_tools` (OFF by default, sent fresh per message, gated
client-side behind the `execute` capability) and `caller_permissions`
(derived from the existing coarse capability model) are both genuinely
sent on every `POST /ai/chat` call, and tool calls are recorded and
shown with their real status including denials. The backend takes both
values from the request body at face value, with **no cross-check
against the caller's real JWT-derived role** — documented here and in
`backend-v1-integration-limitations.md` as never a security boundary,
consistent with every prior prompt's "backend performs no permission
check" finding, taken one step further (this backend also trusts a
client-asserted permission *list*, not just a role string it already
decoded).

## Interactive tool-call confirmation — UNAVAILABLE (documented, not implemented)

§19 asks for confirmation before a risky action executes. The real
contract has no round-trip to pause a turn mid-flight for a per-call
"allow this?" prompt — a mutating tool is authorized for the whole
turn or not at all. The composer's pre-emptive, off-by-default consent
toggle is the honest substitute; a genuinely interactive confirmation
dialog was not built because nothing in the backend could make it real
rather than decorative.

## Guardrails and error handling — IMPLEMENTED

A guardrail rejection is a normal `201` response carrying
`guardrail_findings`, never a distinct HTTP status — the UI shows a
calm, generic "filtered for safety" notice and never renders the
backend's raw internal category strings (`instruction_override`,
`private_key`, etc.), which are guardrail-rule implementation details.
A genuine backend failure is a uniform `502`/`AIIOS-AI-0001` for every
failure mode (guardrail infrastructure failure, every model provider
failing, embedding failure) — indistinguishable from each other
without a raw log, and the UI doesn't pretend otherwise, surfacing the
backend's own message.

## Retrieval-augmented answers and sources — IMPLEMENTED

Citations are shown per assistant message and per AI report, with a
relevance score, resolved to a real title (and a link when a URI
exists). A dedicated Knowledge Search preview calls the exact same
retrieval pipeline `/ai/chat` uses internally, so it's a genuine
preview, not a disconnected demo. Document ingestion is real
(`POST /ai/knowledge/documents`) — text-paste only, since
`DocumentIngestRequest` has no file field.

## Recommendations and AI Reports — IMPLEMENTED

Both are real, backend-generated, citation-carrying content — reports
show their complete body inline in the list (there is no
`GET /ai/reports/{id}`, so nothing was hidden behind a detail page
that couldn't exist), and recommendations can be accepted or rejected.
Neither list carries a real ordering guarantee the backend provides
(reports have `generated_at`; recommendations have no timestamp field
at all), so only the reports list offers a client-side sort.

## Analytics — IMPLEMENTED, with a corrected label

Usage/cost/latency/feedback statistics from `GET /ai/statistics`, with
an explicit "Recompute" action and a prominent staleness timestamp
(§ pattern established by Reporting/Automation). The backend's own
`agent_usage` field is relabeled "Provider usage" in this UI rather
than perpetuated as-is — it is confirmed (by source inspection) to
group by model provider, not by any agent identifier, since no
`agent_id` column exists to group by. `estimated_cost_usd` carries a
visible caveat: it is based on a hardcoded, incomplete per-token price
table, not a bill.

## Prompt management — IMPLEMENTED (mechanism), admin-gated in the UI

Create, version, approve, roll back, and render prompt templates — all
real, working routes. Gated in this UI behind the coarse capability
model's administrative check, since the backend itself enforces no
ownership or role check on any of these routes beyond basic
existence — a UX precaution, not a security boundary duplicated
client-side.

## Agent attribution — UNAVAILABLE (documented, not implemented)

§ asks for agent-aware presentation. `agent_type` can be requested as
a hint when starting a new conversation, but no response anywhere
reports back which agent actually produced an answer — there is no
`agent_id` on any message, conversation, or chat response. The agent
picker is offered only at conversation start, and no part of this UI
ever presents an agent name as confirmed post-hoc attribution.

## Cross-module context — IMPLEMENTED (the one honest mechanism available)

§41 is satisfied via `AskAiButton`, wired into Alerting, Automation,
Reporting, Monitoring, and the Dashboard: it opens a new conversation
with a plain-text draft referencing the real entity's real name/id,
never sent automatically. No structured context-attachment API exists
on this backend, so nothing beyond a plain-text reference was built —
inventing a context payload the assistant doesn't actually receive
would violate §41's own instruction not to fabricate one.

## Tenant isolation — the worst gap found this session (documented, not fixed)

Every by-id fetch in this service — conversations, prompts, and more —
is confirmed to apply **no organization/tenant filter whatsoever**,
not even the caller-supplied-but-unchecked pattern found in earlier
prompts. This is a backend defect, out of scope to fix under the V1
freeze; this frontend always sends the real, currently-selected
organization on every list call (the one place a filter is actually
applied) and fabricates no client-side tenant check the backend
doesn't enforce. Full citation in
`backend-v1-integration-limitations.md`.

## Memory — READ-ONLY BY DESIGN (not a gap)

`POST /ai/memory` exists but isn't called by this feature — memory is
the assistant's own working context, and there is no delete/expire
route despite an `expires_at` column existing. A write-only,
undeletable "remember this" form would be a one-way door; `MemoryList`
only ever reads.

## Partial failure handling — IMPLEMENTED

Every section (statistics, conversation list, transcript, tool
activity, knowledge documents/search, recommendations, reports,
prompts) fails independently — one unavailable piece of data degrades
only its own section, never the whole page (§35).

## Responsive behaviour — IMPLEMENTED

The assistant workspace collapses from a two-column split to a
single-column stack below `md`, matching the layout-responsive pattern
already established by `SplitPaneLayout`; every other page in this
feature reuses the same responsive list/detail patterns as
Monitoring/Alerting/Reporting/Automation.

## Accessibility — IMPLEMENTED (foundation, unchanged this prompt)

Built entirely on already-accessible primitives (`Button`, `Switch`,
`StatusBadge`/`StatusIndicator`, `EmptyState`, `SectionState`, native
`<textarea>`/`<select>`/`<input>`) — the composer's Enter-to-send/
Shift+Enter-newline behavior and the mutating-tools toggle's real
`role="switch"` input are the only new interaction patterns, and both
are built on existing accessible primitives rather than bespoke ones.

## Dashboard / cross-module integration — IMPLEMENTED

Beyond the "Ask AI" entry points above: no duplicate
alert/automation/report-fetching logic was created inside this
feature (§28) — it only ever reads its own `ai-assistant-service`
data, never re-fetching another service's data a prior prompt's
feature module already owns.

See `../backend-v1-integration-limitations.md` for the full,
cross-prompt list with source citations.
