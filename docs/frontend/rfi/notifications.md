# Notification Center

Per Prompt 016 §52, this honestly separates **IMPLEMENTED** from
**PLANNED**/**UNAVAILABLE** for the Enterprise Notification Center
Experience, built against `notification-center-service`'s real
per-recipient `Notification` model. See `../rfi/README.md` and
`../developer-guide/notifications.md` for the full technical reasoning.

## Centralized notification experience — IMPLEMENTED

A real notification bell (wired for the first time in this prompt —
previously a documented, honest empty-state stub), popover preview,
Notification Center list, and detail page, all against real V1 data.
Four related concepts (Notification, Audit Event, Announcement, Alert)
are kept strictly distinct — never merged visually or technically, per
§3's own instruction.

## Operational awareness — PARTIALLY IMPLEMENTED (no unread count, no real-time)

**No unread-count route exists on this backend** — a repository
method for it is real but unused by any route, confirmed by source
inspection. The bell therefore never shows a number, only a plain
indicator dot derived from a small, bounded, already-fetched page —
never a total computed by paginating the full history, which §10
explicitly forbids. **No real-time delivery mechanism exists either**
(no WebSocket/SSE route anywhere in this service) — the bell polls a
real endpoint every 60 seconds, a genuine, working refresh, never a
fabricated push channel.

## User-specific notifications — IMPLEMENTED (with an important caveat)

The list is scoped to the signed-in user via a real `user_id` query
parameter. **This scoping is client-supplied and not verified by the
backend** — see "Permission-aware delivery" below.

## Permission-aware delivery — THE SESSION'S MOST SEVERE FINDING

Reading, viewing, marking read, and acknowledging a notification all
require **no authentication at all** on this backend — confirmed
absent, not merely unenforced, and confirmed on state-mutating routes,
not only reads. A permanent, high-severity warning is shown on the
Notification Center itself, not left to a footnote. This frontend's
own nav gating and its use of the real signed-in user's id are
conveniences for a well-behaved client, never a security boundary —
the backend remains, in principle, the sole authority, even though
today it exercises none.

## Notification routing — PARTIALLY IMPLEMENTED (no deep links)

**No structured link from a notification to the resource that caused
it exists on this backend** — confirmed absent (only free-text
`sourceService`/`sourceEventType` hints and an undocumented metadata
blob). Clicking a notification opens its own real detail page; it does
not, and cannot honestly, navigate on to an alert, automation
execution, report, or asset. Source information is shown as plain
text.

## Configurable preferences — IMPLEMENTED (already existed, reused, not duplicated)

Real per-user notification preferences and per-organization channel
configuration were already built in Prompt 013 under **Settings →
Notifications**. This Notification Center links there rather than
rebuilding the same controls in a second location, per §28's own
instruction.

## Accessibility — IMPLEMENTED (foundation)

Built on already-accessible primitives (`Popover`, `Tabs`, `Alert`,
the same responsive table/card pattern used since Infrastructure). The
bell's unread indicator has a real, descriptive `aria-label` rather
than relying on a purely visual dot.

## Responsive UX — IMPLEMENTED

Desktop popover + full center list; mobile falls back to the same
card-based list pattern established across every prior list feature
this session — never a desktop-only popover forced onto a small
screen.

## Extensibility — PARTIALLY IMPLEMENTED (viewer scope only, by choice)

This is a Notification Center for a recipient viewing their own inbox,
not a notification-authoring console. `create`/`send`/`broadcast`/
`cancel` are real routes, deliberately not exposed here — see the
developer guide's own restraint rationale, matching this session's
established pattern (Prompt 014's rbac-catalog restraint, Prompt 015's
GRC-management restraint) of not building a capability that would
imply a persona the current prompt doesn't serve.

See `../backend-v1-integration-limitations.md` for the full,
cross-prompt list with source citations.
