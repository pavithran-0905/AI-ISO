# Status System

Source of truth: `lib/status.ts`. One canonical taxonomy — no future
feature module may invent its own status color or icon (§18); it looks
its state up here instead.

## Two axes, deliberately distinct

A **tone** (`success`/`warning`/`danger`/`info`/`neutral`/`pending`/
`running`/`stopped`/`degraded`/`unknown`, §5) is a CSS-level color
token defined in `app/globals.css`. A **named state** (§18's
`Healthy`/`Warning`/`Critical`/`Failed`/`Running`/`Stopped`/`Pending`/
`Queued`/`Completed`/`Cancelled`/`Unknown`/`Degraded`/`Maintenance`) is
a business-level vocabulary word that resolves to exactly one tone.
Two named states can legitimately share a tone — `Healthy` and
`Completed` are both genuinely positive outcomes, so both resolve to
`success`.

## The mapping

| Named state | Tone | Icon |
|---|---|---|
| Healthy | `success` | `CheckCircle2` |
| Warning | `warning` | `AlertTriangle` |
| Critical | `danger` | `AlertOctagon` |
| Failed | `danger` | `XCircle` |
| Running | `running` | `Activity` |
| Stopped | `stopped` | `Square` |
| Pending | `pending` | `Clock` |
| Queued | `pending` | `ListOrdered` |
| Completed | `success` | `CheckCircle2` |
| Cancelled | `neutral` | `Ban` |
| Unknown | `unknown` | `HelpCircle` |
| Degraded | `degraded` | `TrendingDown` |
| Maintenance | `neutral` | `Wrench` |

## Usage

```tsx
import { StatusIndicator } from "@/components/data-display/status-indicator";

<StatusIndicator state="running" />
<StatusIndicator state="degraded" label="2 of 6 nodes degraded" /> {/* overrides only the label, keeps the tone/icon */}
```

For a tone/label combination that genuinely isn't one of the 13 named
states (rare — most operational states fit), use `StatusBadge`
directly with an explicit `tone`. Don't extend `STATUS_TAXONOMY` for a
one-off; add a new named state only when it's a real, reusable
operational concept a second feature will also need.
