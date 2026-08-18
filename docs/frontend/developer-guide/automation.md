# Automation

The Enterprise Automation, Workflow & Job Orchestration Experience
built in Prompt 009, on top of the Dashboard's `organization/` context
(Prompt 005) and the patterns established by Monitoring/Alerting/
Reporting (Prompts 006–008). Covers two separate feature modules —
`features/automation` and `features/workflows` — because they're built
against two separate, independently-owned backend services with
different data models and status vocabularies. See
`docs/frontend/rfi/automation.md` for the implemented-vs-planned split
and `docs/frontend/backend-v1-integration-limitations.md` for every
gap discovered building this.

## Which services, and why two modules

| | `automation-service` | `workflow-runtime-service` |
|---|---|---|
| Unit of work | A single script/playbook ("job") | A DAG of nodes ("workflow") |
| Frontend module | `features/automation` | `features/workflows` |
| Execution status (8 vs 12 values) | `pending/running/paused/completed/failed/cancelled/timed_out/rolled_back` | `created/queued/waiting/running/paused/checkpointed/retrying/completed/cancelled/failed/rolled_back/archived` |
| Per-node step breakdown | No route (rows exist, unreachable) | Real: `GET /workflow-instances/{id}/steps` |
| Human approval gates | Doesn't exist | Real: `GET .../approvals`, `POST .../decide` |

The two status enums share only five string values and disagree on
everything else — `pending` vs `created`/`waiting`, `timed_out` with no
workflow equivalent, `checkpointed`/`retrying`/`archived` with no
automation equivalent. `features/automation/lib/status-maps.ts` and
`features/workflows/lib/status-maps.ts` are two independent maps onto
the canonical `StatusState` taxonomy for exactly this reason — merging
them would silently mistranslate one service or the other.

## Feature structure

```
features/automation/
├── api/          jobs-api.ts, executions-api.ts, statistics-api.ts, execution-mapper.ts
├── hooks/        use-jobs.ts, use-executions.ts
├── components/   ~10 components: tables, filters, RunAutomationDialog,
│                  JobActions, VariablesEditor, ExecutionLogViewer
├── types/        index.ts — real enums/schemas from source inspection
├── lib/          duration.ts, execution-variables.ts, status-maps.ts
└── pages/        7 pages (Overview, Automations list/new/detail/edit,
                   Executions list/detail)

features/workflows/
├── api/          workflows-api.ts
├── hooks/        use-workflows.ts
├── components/   WorkflowActions, InstanceDetailView, sub-nav
├── types/        index.ts
├── lib/          status-maps.ts
└── pages/        4 pages (Workflows list/detail, Instances list/detail)
```

Both follow §29's flow: `Page → Hook → API module → apiClient → real V1 endpoint`.

## Real endpoint inventory

Confirmed by direct source inspection, never inferred from route
names. `automation-service`: 17 non-health routes across
`app/api/jobs.py`, `executions.py`, `templates.py`, `statistics.py`,
`reports.py`. `workflow-runtime-service`: 20 non-health routes across
`app/api/workflows.py`, `instances.py`, `statistics.py`, `reports.py`.

Key points:

- `GET /automation/jobs` and `GET /workflows` accept only
  `organization_id` — no pagination, search, filter, or sort. Both
  return their organization's complete result unpaginated, so every
  list-shaping operation in this feature runs client-side over that
  complete set — nothing is hidden behind a page boundary.
- `GET /automation/executions` additionally accepts `status`;
  `GET /workflow-instances` too. Both real, server-side.
- Running is **asynchronous** in both services: the execute/run
  endpoints create a `pending`/`created` record and enqueue the real
  work for a background worker. Neither service exposes a WebSocket or
  SSE endpoint (confirmed by source inspection of both) — every
  "live" view in this feature polls (`useExecution`/`useWorkflowInstance`
  poll every 5s while the run is active, and stop once it reaches a
  terminal status).
- `PUT /automation/jobs/{id}` is a **full replace** whose schema
  defaults `status` to `draft` — see "The PUT status trap" below.
- Cancel/pause/resume act on a **job/workflow id**, not an execution/
  instance id — the backend resolves "the currently active run" itself
  and 404s when there isn't one.

## The PUT status trap

`AutomationJobUpdateRequest.status` defaults to `JobStatus.DRAFT`
server-side. An update that omits `status` therefore silently demotes
a live automation to draft. `AutomationJobUpdateInput` (the frontend
type) makes every field required for exactly this reason —
`JobForm`/`AutomationEditPage` always send the job's current status
explicitly, and the status control only appears in the edit form (not
create, where the backend hard-codes `active` and ignores any client
value regardless).

## The `_target_ids` leak

An execution's selected targets have no first-class field on
`AutomationExecutionResponse` — the backend stores them inside the
execution's own `variables` dict under an internal `_target_ids` key
(`app/services/execution.py`), so they round-trip back mixed in with
the operator's real variables. `features/automation/lib/execution-variables.ts#splitExecutionVariables`
separates the two so neither is shown as the other; `ExecutionDetailView`
renders them as distinct "Variables" and "Targets" sections.

## No parameter or target APIs — why variables are free-form

`automation-service` has a complete `AutomationParameter` model,
schema, service layer, and DI wiring — and zero routes. Its
`parameter_type` isn't even an enum (a plain unvalidated string), and
there is no `is_secret`/`allowed_values`/`min`/`max` anywhere. Likewise
`AutomationTarget` has a full model and repository but no routes at
all — targets can be neither listed nor created, so no target picker
was built; a run with no `target_ids` executes locally on the
automation-service container, which `RunAutomationDialog`'s
confirmation step states explicitly. `VariablesEditor` is therefore a
plain key/value editor, not a schema-driven typed form — building the
latter against a schema that can't be fetched would be exactly the
invention §13 forbids. See `backend-v1-integration-limitations.md`.

## Dispatch reality — `RUNNABLE_PLAYBOOK_TYPES`

Only `shell_script`, `bash`, `python_script`, `powershell`, and
`ansible_playbook` are ever successfully dispatched
(`app/dispatchers/execution_dispatcher.py`) — `tosca_service_template`,
`custom_plugin`, `workflow_task`, and `future_dsl` always raise
`DispatchError`. `RUNNABLE_PLAYBOOK_TYPES` in `features/automation/types`
encodes this, and both the job form and the run dialog show an honest
warning rather than letting an operator discover it only after a
failed run.

## Mutation architecture and safety

Every mutation across both modules waits for the backend's confirmed
response before the UI reflects it (§32: "do not use unsafe optimistic
updates for infrastructure operations") — Run/Pause/Resume/Cancel can
change real infrastructure state, so this matters more here than in a
read-mostly feature. `RunAutomationDialog`/`WorkflowActions`' run flow
is a real two-step Configure → Confirm sequence (§10/§38): the confirm
step shows the automation/workflow name, its variables, and (for
Automation) an explicit "runs on the AI-IOS automation host" line,
before the button — labeled "Run Automation"/"Run Workflow", never
something ambiguous — becomes clickable. `Button`'s own `loading` prop
disables it for the mutation's duration, preventing a duplicate
submission (§12).

Resume needs special handling: the backend's own response to
`POST .../resume` still reports the pre-resume status (it only flips
once a worker picks the run back up), so `JobActions`/`WorkflowActions`
show "Resuming run" rather than claiming the run is now active.

## Permission handling

Same mechanism as Reporting: mutation buttons are gated by the coarse
role capability model, mapped onto the closest of the 9 real actions
since neither service defines its own vocabulary — Run/Pause/Resume/
Cancel → `execute`; Edit → `update`; Delete → `delete`; deciding a
workflow approval → `approve` (the one exact match in the vocabulary).
Both services check no permission on any route at all (confirmed by
source inspection — every route uses only `Depends(get_current_user_id)`),
so this is purely a UX convenience per §25.

**Worth flagging beyond the frontend's own scope**: `scheduler-service`
additionally leaves 30 of 42 routes with **no authentication dependency
at all** (not even the id-only check the others share), and none of
the three services scope `organization_id` by tenant — every
repository is constructed without the `tenant_scope` argument its own
base class accepts. The frontend still always sends the real,
currently-selected `organization_id`. See
`backend-v1-integration-limitations.md`.

## Error handling

Every section is its own `useQuery` + `SectionState` — one failing
independently never blanks the rest of the page (§35). A rejected
Cancel/Pause/Resume shows the backend's own real message (e.g. "no
active execution for this job"), not a generic failure — see
`JobActions`/`WorkflowActions`.

## Navigation / information architecture

`lib/route-registry.ts`: `automation` (`/automation`) and `workflows`
(`/workflows`) are the only entries shown in the primary sidebar;
`automation-automations`, `automation-executions`, and
`workflow-instances` are registered `"implemented"` (so the command
palette can find them) but `showInNav: false` — reachable via each
feature's own sub-nav, mirroring Monitoring/Alerting/Reporting. Dynamic
id routes aren't registered at all — each detail page renders its own
"Back to…" action instead.

## Dashboard integration

`features/dashboard`'s own automation-execution fetching (Prompt 005's
`automation-api.ts`/`use-automation-executions.ts`) is deleted and
consolidated into `features/automation` (§28) — `RecentActivitySection`
now consumes `useExecutions` from the canonical module and links each
execution to its own `/automation/executions/{id}` detail page. The
Dashboard's KPI grid "Automations" tile now links to
`/automation/automations`, and "Recent automation activity"'s heading
carries a "View in Automation" link — both previously unlinked since
neither `/automation` nor `/workflows` existed until this prompt.

## Monitoring / Alerting integration

Neither exists. Confirmed by source inspection: no field on
`AutomationJob`/`AutomationExecution`/`Workflow`/`WorkflowInstance`
references an inventory asset or an alert, and no client in either
service calls `inventory-service` or `alerting-service` from any
reachable code path (`automation-service`'s own `InventoryClient` is
fully implemented but never wired to a route — dead code, exactly the
same pattern as Alerting's own dead `InventoryClient` found in Prompt 007).
No cross-links were fabricated. See
`backend-v1-integration-limitations.md`.
