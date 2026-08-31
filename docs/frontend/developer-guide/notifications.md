# Notification Center

Built in Prompt 016 against `notification-center-service`'s real
per-recipient `Notification` model — `GET /notifications`,
`GET /notifications/{id}`, `POST /notifications/{id}/read`,
`POST /notifications/{id}/acknowledge`,
`GET /notifications/{id}/deliveries`. See
`docs/frontend/rfi/notifications.md` for the implemented-vs-planned
split and `docs/frontend/backend-v1-integration-limitations.md` for
the full gap list with citations.

## Terminology: four real, distinct concepts, never merged (§3)

This service alone exposes three of them, each with its own model and
its own frontend feature:

| Concept | Model | Frontend feature |
|---|---|---|
| **Notification** | `Notification` (`app/models/notification.py`) | This one — Prompt 016 |
| **Audit Event** | `NotificationAudit` (`app/models/governance.py`) | Prompt 015's Audit, as the `notifications` source |
| **Announcement** | `NotificationAnnouncement` (`app/models/announcement.py`) | Not built — a pinned-bulletin-board content object, out of this prompt's own IA |
| **Alert** | `alerting-service`'s own, entirely separate `AlertNotification`/`Alert` models | Prompt 007's Alerting |

**"Alert → Notification" (§29) is not real.** Confirmed by grepping
`alerting-service`, `automation-service`, and `reporting-service` for
any call into `notification-center-service`: zero matches.
`alerting-service` dispatches its own notifications through its own,
independent `AlertNotificationService` and `shared_core.notifications`
instance — it never creates a row in this service's `notifications`
table. An alert firing does not produce anything a user would see in
this Notification Center.

## The most severe permission finding of the session

`GET /notifications` (list), `GET /notifications/{id}` (detail),
`POST /notifications/{id}/read`, `POST /notifications/{id}/acknowledge`,
and `GET /notifications/{id}/deliveries` **require no authentication at
all** — confirmed absent, not merely unenforced (none declares a
caller-identity dependency). Worse than Prompt 015's finding on this
same service's audit routes: here the unauthenticated routes include
**state-mutating** ones (mark read, acknowledge). `organization_id`
and `user_id` are both plain, caller-supplied query parameters on
`GET /notifications`, never derived from or cross-checked against the
JWT — anyone who can reach the API could read or mutate any
organization's or any user's notifications by supplying a different id.

**Frontend behavior**: a permanent, severe `Alert` (tone `danger`, not
`warning`) on the Notification Center page states this plainly. The
list still sends the real, currently-signed-in user's own id
(`useSession().userId`) as `user_id` — the only honest choice, since
there is no server-side alternative — but this is documented
everywhere as a convenience, never a security boundary.

## No unread-count route; the bell never shows a number

`NotificationRepository.count_unread(organization_id, user_id)` is a
real, working repository method — confirmed unused by any route
(grepped the whole service). §10 explicitly forbids computing a total
from paginated client data, so `NotificationArea`
(`components/navigation/notification-area.tsx`) and
`useRecentNotifications` never render a count: only a plain dot
indicating whether *any* item in a small, bounded, most-recent page
(`limit=8`, the same data the popover itself displays — no second
call) has `readAt === null`. A light 60-second `refetchInterval` (a
real, working TanStack Query poll — not a fabricated push mechanism;
none exists on this service, confirmed absent by grepping for
WebSocket/SSE handlers) keeps this reasonably current.

## "Unread" and "Important" are client-side quick views, not server filters

`GET /notifications` supports exactly `user_id`, `status` (one
`NotificationStatus` value), `category`, `source_service` — no
`priority` filter, and no single status value cleanly means "unread"
(unread is `readAt === null`, which spans several statuses:
`sent`/`delivered`/etc., everything before `read`/`acknowledged`).
`NotificationCenterPage` applies "Unread"/"Important" as a client-side
filter over the already-fetched page (`applyQuickView`), switching
tabs never triggers a new fetch — the same rule Prompt 015 established
for Table/Timeline. The real `category`/`status` filters are offered
separately, unfiltered by quick view, as genuine server-side queries.

## No deep-link field — confirmed absent, not merely unbuilt

`Notification` has no `entity_type`/`entity_id` pair and no typed
foreign key to another service's record — only free-text
`sourceService`/`sourceEventType`/`correlationId` hints and an
unstructured `metadata`/`tags` JSON blob with no documented schema.
§16's "Notification → Alert detail / Automation execution / Report /
Asset / Audit event" deep links are **not built** — parsing
`notification_metadata` speculatively to guess a link would risk
navigating to the wrong (or a nonexistent) resource, and the prompt's
own instruction is explicit: only use confirmed routes and
identifiers. `sourceService`/`sourceEventType` are shown as plain
text on the detail page, never as a link.

## Mark read vs. acknowledge — real, separate, never confused (§23)

`POST /{id}/read` and `POST /{id}/acknowledge` are two distinct,
idempotent routes. Acknowledging also stamps `read_at` server-side if
unset (confirmed: `NotificationService.acknowledge`), so an
acknowledged notification always shows as read too, never the reverse
— `NotificationDetailView` hides "Mark read" once `readAt` is set and
hides "Acknowledge" once `status === "acknowledged"`, rather than
showing two controls that could contradict each other.

**"Mark as unread" and "mark all read" are both confirmed absent** —
no `mark_unread` method exists anywhere in the service, and no bulk
route exists (grepped `app/api/*.py`). Composing "mark all" from N
individual `/read` calls was deliberately not built: partial failure
across N real mutations would need careful UX this prompt's own scope
doesn't ask for, and it risks misrepresenting a batch operation the
backend doesn't actually support as a single atomic one.

## Deliberately out of scope: authoring/admin actions

`POST /notifications` (create), `/send`, `/broadcast`,
`DELETE /notifications/{id}`, and `POST /notifications/{id}/cancel`
are all real routes, not built into this UI — they're actions a
notification's *sender/administrator* would take, not a recipient
viewing their own inbox. `cancel` specifically withdraws a
not-yet-terminal notification before dispatch, which doesn't fit a
"Notification Center" persona either. This mirrors Prompt 014's
restraint around rbac-service's catalog-editing routes: real
capabilities, deliberately not exposed where building them would imply
a persona this feature doesn't serve. The still-`planned()`
`notifications-admin` route in `lib/route-registry.ts` ("Multi-channel
delivery: templates, preferences, subscriptions, digests") is the
right home for that surface in a future prompt.

## Preferences and channels live in Settings — not duplicated

`GET/PUT /notifications/preferences` and `GET/PUT
/notifications/channels/{channel}` were already built in Prompt 013
(`features/settings/api/notifications-api.ts`,
`features/settings/pages/notifications-page.tsx`). This feature never
re-implements them — the Notification Center's header links to
`/settings/notifications` instead (§28's own instruction). The two
feature modules touch entirely disjoint route sets:
`features/notifications` never calls `/preferences` or `/channels`,
and `features/settings`'s notification module never calls
`/notifications` (the list), `/read`, `/acknowledge`, or `/deliveries`.

## Deliveries — a real, separate per-channel concept

`GET /notifications/{id}/deliveries` lists one row per channel a
notification resolved to and was dispatched over (a notification with
both email and Slack preferred fans out into two `NotificationDelivery`
rows). This is genuinely distinct from the notification's own
`status`/`readAt` (whether the recipient has seen it) — shown as its
own section on the detail page, never merged into the notification's
own status badge.

## API architecture

```
Notification Center Page → Notification Hooks (features/notifications/hooks/use-notifications.ts)
                          → Notification API module (features/notifications/api/notifications-api.ts)
                          → apiClient (@/api/client)
                          → Backend V1
```

Sensitive-metadata masking (`lib/mask-sensitive.ts`, applied to
`notification.metadata` before rendering) is shared with Prompt 015's
Audit feature — promoted out of `features/audit/lib/` into the
top-level `lib/` once a second feature needed the identical logic.

## A note on `notification-center-service`'s own report/export pipeline

Prompt 015's own limitations entry claimed
`notification-center-service` has no report-generation route "of any
kind." **This session's own further research (during this prompt)
found that claim incorrect**: a real `POST/GET /notifications/reports`,
`GET /notifications/reports/{id}`, `GET
/notifications/reports/{id}/download` pipeline exists
(`app/api/analytics.py`, `NotificationReport` model). Corrected in
`docs/frontend/backend-v1-integration-limitations.md`. Not retrofitted
into Prompt 015's already-shipped Audit export control as part of this
prompt — that stays a candidate for a small, separate follow-up rather
than reopening a different prompt's finished scope mid-stream.
