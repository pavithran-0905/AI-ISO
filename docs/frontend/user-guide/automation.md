# Automation

Where to see what automation exists, run it safely, and follow what
happens. Covers two related but separate areas — **Automation** (single
scripts/playbooks) and **Workflows** (multi-step DAGs) — because they're
two different backend services with two different vocabularies. Only
documents what's actually implemented — there's no scheduling or target
picker yet (see Known limitations).

## Automation Overview

Open **Automation** from the sidebar (or `/automation` directly). It
shows the same organization you've already picked on the Dashboard.

- **Summary** — real counts and a success rate, with a clear note on
  when they were last computed. AI-IOS does not recompute these
  automatically, so the numbers can be old — the sections below it are
  always live.
- **Running now** — every automation that's pending, running, or
  paused right now.
- **Needs attention** — automations that recently failed or timed out.

## Automations

Open **Automations** from the tab bar, or `/automation/automations`.
Every automation job defined for your organization.

- **Search** — matches name, description, and tags, over the complete
  list for your current filters.
- **Filters** — narrow by Status or Type.
- **Sort** — click a column header to sort by it.

Click **New automation** to create one, or an automation's name to
open its detail page.

## Creating and editing an automation

An automation needs a name, a type, a playbook type, and its script
content. AI-IOS can currently run shell, bash, Python, PowerShell, and
Ansible content — anything else is accepted but will fail when you try
to run it, and the form tells you so.

Once created, every field can be edited, including its status
(Draft/Active/Disabled/Archived) — editing is a full replace, so make
sure the status is set the way you want it every time you save.

## Automation detail

Shows an automation's configuration, its content, its default
variables, its available actions, and its recent runs.

## Running an automation

Click **Run Automation**, review the variables it will use, then
confirm. The confirmation step shows exactly what's about to happen
before anything runs. Every automation runs on the AI-IOS automation
host itself — there's no target picker to choose a different machine
(see Known limitations).

Nothing runs until you confirm, and the button is disabled the moment
you click it so a second click can't start a duplicate run.

## Variables

Variables are free-form name/value pairs, stored with the automation
and with each run for reference. AI-IOS does not insert them into the
script content — if your script needs a value, it must read it another
way (an environment variable your script sets up itself, for example).

## Pause, Resume, Cancel

These act on an automation's current run, whichever one is active.

- **Pause** stops scheduling further work; anything already running
  keeps going.
- **Resume** puts it back in the queue — it may take a moment to
  actually start running again.
- **Cancel** requires confirmation, and AI-IOS never shows "Cancelled"
  until it's confirmed. Like Pause, work already in flight finishes on
  its own rather than stopping mid-step.

There's no separate Retry action — start a fresh run with Run
Automation instead.

## Executions

Open **Executions** from the tab bar, or `/automation/executions`.
Every run recorded for your organization, filterable by status and by
which automation produced it.

## Execution detail

Shows a run's status, timestamps, computed duration, the variables it
used, which targets it ran against (if any), and its output.

## Output

Each run's real output is shown as one block per step — search it,
filter by severity, or copy it. While a run is still active, output
refreshes automatically; once it finishes, it stops.

## Workflows

Open **Workflows** from the sidebar. A workflow is a multi-step
process (a DAG of nodes) rather than a single script.

- **Workflows** lists every workflow definition for your organization.
- Click one to see its details, run it, and see its recent instances.
- **Instances** (the tab bar, or `/workflows/instances`) lists every
  run across every workflow, filterable by status.

## Workflow instance detail

Shows the run's identity and timestamps, plus three things Automation
doesn't have:

- **Approvals** — if the workflow has a human-approval step, you'll
  see it here. If you're listed as an approver, you can approve or
  reject it directly, with an optional comment.
- **Steps** — a real breakdown of every node in the workflow, its own
  status, and its own output or error.
- **Logs** — the run's real output.

## Troubleshooting

- **A section says "Access denied."** Your account doesn't have
  permission to view that specific data — contact your administrator.
- **A section shows an error with a Retry button.** That data is
  temporarily unavailable; the rest of the page keeps working
  normally.
- **I don't see Run/Edit/Delete, or Pause/Resume/Cancel.** Your role
  doesn't currently allow that action.
- **Pause/Resume/Cancel failed.** The message tells you why — usually
  that nothing is currently running for that automation.
- **An automation or workflow I ran shows a warning about its
  playbook/node type.** AI-IOS can't dispatch every content type yet;
  the warning tells you before you waste a run finding out.

## Known limitations

- **No target picker.** Every automation runs on the AI-IOS automation
  host itself; there's no way to choose a different machine from this
  interface yet.
- **No typed parameter forms.** Automations use free-form variables,
  not a declared, validated parameter schema.
- **No scheduling.** Recurring automation runs aren't available from
  this interface yet.
- **No Retry action.** Start a fresh run instead.
- **A generation's exact output isn't kept forever in a browsable
  form** beyond the logs shown on its own execution/instance page.
