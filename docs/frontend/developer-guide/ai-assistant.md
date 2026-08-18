# AI Assistant

The Enterprise AI Assistant & Intelligence Experience built in
Prompt 010, against `services/ai-assistant-service` — the first
prompt this session where a single backend service exposes this many
independently-routable subsystems (chat, knowledge/RAG, insights,
catalog, prompts) behind one `/ai` prefix. See
`docs/frontend/rfi/ai-assistant.md` for the implemented-vs-planned
split and `docs/frontend/backend-v1-integration-limitations.md` for
every gap found building this — this prompt added more entries there
than any prior one, including the worst tenant-isolation gap found all
session.

## Real endpoint inventory

Confirmed by direct source inspection of `app/api/chat.py`,
`insights.py`, `knowledge.py`, `agents.py`, `prompts.py` — 37
non-health routes total. This feature consumes 26 of them:

| Router | Routes | Consumed | Not consumed, and why |
|---|---|---|---|
| `chat.py` | 11 | 5: `POST /ai/chat`, `GET /ai/conversations`, `GET /ai/conversations/{id}`, `.../messages`, `.../tool-calls` | `POST /ai/chat/stream` (fake streaming — see below), `POST /ai/chat/multi-agent` (a second, narrower chat entry point with no citations/tool-call/guardrail fields on its response — §41 covers cross-module context, not a second composer), `POST/GET /ai/sessions`, `.../close`, `.../touch` (a session-grouping concept `Conversation` doesn't require and no UI in this prompt's scope needs) |
| `insights.py` | 9 | 8 | `POST /ai/memory` (create) — Memory is deliberately read-only in this feature; see "Memory is read-only" below |
| `knowledge.py` | 3 | 3 (all) | — |
| `agents.py` | 7 | 3: `GET /ai/agents`, `GET /ai/tools`, `GET /ai/models` | `POST /ai/agents`, `POST /ai/tools` (create), `POST /ai/tools/execute` (direct execution bypassing a conversation), `POST /ai/models/select` — all operator/config-time actions with no V1 CRUD affordance anywhere else in the app either; see "Catalog is read-only" below |
| `prompts.py` | 7 | 7 (all) | — |

## Feature structure

```
features/ai-assistant/
├── api/          chat-api.ts, knowledge-api.ts, insights-api.ts,
│                  catalog-api.ts, prompts-api.ts
├── hooks/        use-chat.ts, use-knowledge.ts, use-insights.ts,
│                  use-catalog.ts, use-prompts.ts
├── components/   ~20 components: conversation-list, message-thread,
│                  message-item, composer, mutating-tools-toggle,
│                  guardrail-notice, tool-call-list, citations-list,
│                  feedback-buttons, document-list, ingest-document-
│                  form, knowledge-search-panel, recommendation-list/
│                  form, ai-report-list/form, ai-statistics-summary,
│                  memory-list, prompt-list/detail/create-form,
│                  recent-conversations-list, pending-recommendations-
│                  list, ask-ai-button, ai-assistant-sub-nav
├── types/        index.ts — 12 enum/type pairs, ~22 interfaces
├── lib/          status-maps.ts, format.ts, caller-permissions.ts
└── pages/        7 pages (Overview, Assistant, Knowledge,
                   Recommendations, Reports, Analytics, Prompts)
```

Follows §29's flow: `Page → Hook → API module → apiClient → real V1
endpoint`, same as every prior feature this session.

## Why `/ai/chat/stream` is not consumed

`app/api/chat.py`'s own module docstring is explicit about this: the
route is a real `StreamingResponse` emitting genuine SSE frames, but
`chat.send(...)` is awaited **in full** before any frame is sent — the
answer is produced completely, then chopped into fixed 256-character
`delta` chunks and dripped out. Total latency to the last byte is
identical to `POST /ai/chat`; the only difference is a cosmetic
typewriter effect with zero time-to-first-token improvement. §10
explicitly forbids faking streaming, and a client can't tell the
difference between "real incremental generation" and "the whole answer
already existed and is being drip-fed" without reading this same
source comment — so `chat-api.ts` consumes only the synchronous
`POST /ai/chat`, with a single "sending" loading state on the Send
button. Documented in `backend-v1-integration-limitations.md`.

## Self-asserted `caller_permissions` / `allow_mutating_tools`

`ChatRequest.caller_permissions: list[str]` and
`allow_mutating_tools: bool` are both taken from the request body
at face value — `app/services/chat.py`'s tool-authorization gate
checks a tool's `required_permission` against this client-supplied
list, never against the caller's real JWT-derived role. This frontend
still populates `caller_permissions` (via
`lib/caller-permissions.ts#derivedCallerPermissions`, mapping the
existing coarse capability model's `PermissionAction`s) for
consistency with how every other feature already sends permission
context — but it is documented, here and in the type's own docstring,
as never a security boundary. `allow_mutating_tools` is exposed as the
composer's own "Allow this assistant to take actions that change
infrastructure" toggle: OFF by default, sent fresh with each message,
and additionally gated client-side behind `can("execute")` — a role
without execute never even sees the control, though nothing stops a
crafted request from setting it true regardless.

## No interactive per-tool-call confirmation

`ChatRequest` has no field to pause a turn mid-flight for a "the
assistant wants to run X, allow?" round-trip, and no such endpoint
exists. `MutatingToolsToggle` is therefore a composer-level, pre-emptive,
OFF-by-default consent sent *with* the request — the only honest
implementation of §19 given this contract. A denied tool call is
still fully visible after the fact (`ToolCallList`, status `denied`
with `denialReason`), just never confirmable in the moment.

## Guardrails are in-band, not a distinct error

A guardrail rejection is not a special HTTP status — `ChatResponse`
still returns `201` with normal `content`, plus a non-empty
`guardrail_findings: list[str]` of raw internal pattern-category
strings (`"instruction_override"`, `"private_key"`, etc. —
`GuardrailVerdict` and the category vocabulary are internal-only,
never a declared enum on any public schema). `GuardrailNotice` takes
only a `findingsCount: number`, never the strings themselves — there
is no prop through which a caller could leak a category name, by
construction. A genuine backend failure is a uniform `502`/
`AIIOS-AI-0001` for every failure mode (guardrail infra failure, every
provider in the fallback chain failing, embedding failure) —
indistinguishable from each other without a raw log; the UI can't and
doesn't pretend to tell them apart, and shows the backend's own
message via `ApiRequestError`.

## Citations: typed despite an untyped schema

`ChatResponse.citations`/`MessageResponse.citations` are declared
`list[dict[str, Any]]` at the Pydantic level — a real, fully-typed
`CitationResponse` schema exists in `app/schemas/chat.py` but is never
actually used as the field's type (confirmed: neither response
constructs one). The runtime shape is fully confirmed by reading the
one function that ever builds a citation dict
(`RetrievedPassage.as_citation()`), so `Citation` in
`features/ai-assistant/types` is typed precisely — the one deliberate
exception to this platform's usual "leave an untyped dict as
`unknown`" discipline, because the shape is genuinely confirmed, not
assumed. `KnowledgeSearchHit` (from `POST /ai/knowledge/search`) is a
real, separately-declared, fully-typed schema with one field a chat
citation never has: the actual retrieved passage `content`.

## Tool calls have no message correlation

`ToolCallResponse` has `conversation_id` but no `message_id` column —
the backend genuinely cannot say which assistant message a given tool
call supported, only which conversation it belongs to. `ToolCallList`
is therefore rendered as its own section below the transcript, never
interleaved into a specific message — interleaving would imply a
correlation the data doesn't have. Denied calls are included in the
list (the backend's own `list_conversation_tool_calls` docstring notes
this is deliberate, so "blocked" is distinguishable from "never
attempted"), with `result: null` for anything that never ran.

## Agent attribution: requestable, never reported

`ChatRequest.agent_type` is a real hint accepted on every call, but no
response anywhere — `ChatResponse`, `MessageResponse`, `Conversation`
— carries an `agent_id`/`agent_type` field back. There is no way to
ask "which agent actually answered this?" after the fact. The composer
therefore offers the agent picker only when starting a brand new
conversation (`Composer`'s own `isNewConversation` check), and nothing
in this feature ever renders an agent name as if it were confirmed
attribution.

## `agent_usage` is a misnomer — relabeled, not renamed

`AiStatisticsResponse.agent_usage` is computed server-side as
`Counter(message.provider for ...)` (confirmed by reading the
statistics snapshot builder) — there is no `agent_id` column
anywhere to group by, so it is, despite its name, a provider
breakdown. `AiStatisticsSummary` shows it under the heading "Provider
usage" rather than perpetuating the backend's own naming mistake, with
`AiStatistics.agentUsage`'s own docstring explaining why. `tool_usage`
is keyed by raw tool UUID strings — `AiStatisticsSummary` resolves
each against `GET /ai/tools` before display, exactly like
`ToolCallList` does for individual calls.

## Memory is read-only

`POST /ai/memory` exists and works, but this feature never calls it —
the assistant is the only realistic writer of its own memory (it's
described as scratchpad-like working context the assistant records for
itself), and there is no delete/clear/expire endpoint at all despite
`AiMemory.expires_at` existing as a column. Exposing a manual "remember
this" form without any way to undo it would be a one-way door this
feature doesn't build. `MemoryList` only ever calls `GET /ai/memory`.

## Catalog (agents/tools/models) is read-only

`GET /ai/agents`/`GET /ai/tools`/`GET /ai/models` are consumed purely
to *label* things elsewhere in the UI — a tool call's `toolId`, a
statistics breakdown's tool-usage keys, the render form's variable
list. No agent/tool creation UI was built: registering an agent or
tool is an operator/config-time activity with no V1 CRUD affordance
anywhere else in the app either, and `POST /ai/tools/execute` (direct
execution bypassing a conversation entirely) has no product surface
this prompt's scope calls for. `ModelProviderResponse.is_default` is
computed as "alphabetically first configured provider"
(confirmed: `enumerate(available)`, `index == 0`) — not a real
configured default — so it is deliberately never rendered as a
"default" badge anywhere, kept on the type only for completeness.

## Prompts: real versioning, zero real enforcement

`app/api/prompts.py` implements genuine versioning/approval/rollback
state transitions, but every route accepts any authenticated caller —
there is no ownership or role check on approve/rollback beyond basic
existence. `PromptsPage` gates create/add-version/approve/rollback
behind `isAdministrative` (the coarse capability model's admin check)
as a UX-only precaution; render is left open to everyone since it
mutates nothing. See `PromptDetail`'s own docstring.

## Cross-tenant reads — the worst instance of this pattern all session

Confirmed by source inspection: **every single by-id fetch in this
service — `get_conversation`, the prompt routes' `get_by_id`, tool
lookups by key — constructs its repository call with no
`organization_id`/tenant filter at all**, not even the "trusts the
caller-supplied param" pattern found in earlier prompts this session.
A valid UUID for any organization's conversation, prompt, or resource
returns its real data to any authenticated caller who guesses or
otherwise obtains the id. This frontend still always sends the real,
currently-selected `organization_id` on every list call (the one place
a filter is actually applied), and never fabricates a client-side
tenant check the backend doesn't itself enforce. See
`backend-v1-integration-limitations.md` for the full citation.

## Mutation architecture

Every mutation (send, generate recommendation/report, submit feedback,
ingest, decide, add/approve/rollback a prompt version) waits for the
backend's confirmed response before the UI reflects it — no optimistic
updates, consistent with every prior feature. `useSendMessage`'s
`onSuccess` invalidates the whole `["ai-assistant", "conversations"]`
query-key prefix in one call (covers the conversation list, the sent
conversation's messages, and its tool calls), since a send with no
`conversationId` also creates a brand-new conversation the cached list
doesn't know about yet.

## Permission handling

Same mechanism as every prior feature: the coarse role capability
model, mapped onto the closest of the 9 real `PermissionAction`
values since this service defines no permission vocabulary of its own
— generate/ingest → `create`; decide a recommendation → `approve`;
prompt admin actions → `isAdministrative`; the mutating-tools toggle →
`execute`. `services/ai-assistant-service` performs no real permission
check on any route (every route depends only on
`Depends(get_current_user_id)`) — this is a UX convenience only, per
§25, layered on top of the cross-tenant gap above.

## Navigation / information architecture

`lib/route-registry.ts`: the "ai-assistant" `planned()` stub is
promoted to a 7-entry `implemented()` family under `/intelligence` —
the root (`intelligence`, shown in the primary sidebar) plus 6
sub-pages (`assistant`, `knowledge`, `recommendations`, `reports`,
`analytics`, `prompts`, all `showInNav: false`, reachable via
`AiAssistantSubNav`) — mirroring Reporting's/Automation's own
overview-plus-sub-nav shape. The separate, still-`planned()` entries
for `ai-agents`, `prompt-management` (the platform-wide theoretical
service, distinct from this service's own real `/ai/prompts`),
`rag` (the separate, unconnected `rag-service`), `document-intelligence`,
and `knowledge-graph` are untouched — none of them map to what this
prompt actually built against `ai-assistant-service`.

`/intelligence/assistant` reads `?conversation=<id>` and `?draft=<text>`
from its own search params: the former lets `RecentConversationsList`
and every cross-module "Ask AI" link open a specific conversation
directly (`router.replace` keeps the URL in sync as the user switches
conversations); the latter is what `AskAiButton` uses to pre-fill the
composer — read once via `useState`'s lazy initializer, never
re-applied on prop change, and never auto-sent.

## Cross-module "Ask AI" entry points

`AskAiButton` (`draft?: string`) is wired into `AlertActions`,
`JobActions` (Automation), `ReportActions` (Reporting),
`AssetDetailView` (Monitoring), and the Dashboard's own page header.
Each passes a plain-text draft referencing the real entity's real
name/id (`Tell me about alert "${alert.title}" (id: ${alert.id}).`) —
never a structured context payload, since no context-injection API
exists on this backend (see `backend-v1-integration-limitations.md`).
The Dashboard's entry point carries no entity reference (an empty
draft opens a blank composer) since it isn't tied to one.

## Error handling

Every section is its own `useQuery` + internal loading/error handling
(`SectionState` at the page level, ad-hoc checks inside list
components) — one section failing never blanks the rest of a page. A
failed send keeps the typed message in the composer rather than
clearing it, since nothing persists server-side on failure — "retry"
is just pressing Send again.
