# Settings

Per Prompt 013 §53, this honestly separates **IMPLEMENTED** from
**PLANNED**/**UNAVAILABLE** for the Enterprise Configuration, Settings
& Administration Experience — the widest backend surface of any
single prompt this session, across seven services. See
`../rfi/README.md` for the foundation this builds on and
`../developer-guide/settings.md` for the full technical reasoning
behind every scope decision below.

## Enterprise configuration management — IMPLEMENTED (across 7 real services, 0 fabricated)

My Preferences, Security, Organization, Projects, Integrations, and
Notifications are all backed by real, source-confirmed routes across
`user-management-service`, `authentication-service`,
`organization-service`, `project-service`, `integration-hub-service`,
and `notification-center-service`. No dedicated "settings-service"
exists — confirmed absent — this feature is a genuine cross-service
aggregation, not a wrapper around one backend module.

## Permission-aware settings — IMPLEMENTED (mechanism; three different real authorization shapes, none client-verifiable)

Organization/Projects/System edit controls are gated by the existing
coarse `isAdministrative` role heuristic. The real backend
authorization underneath is genuinely different per service (per-
organization membership role, a JWT `roles` array claim, or no check
at all) and none of the three is something this frontend can verify
live — see the developer guide's "Why a coarse permission heuristic"
section. The backend remains the sole authority in every case.

## Integration management — IMPLEMENTED (generic connector framework, real lifecycle)

Register, configure, test, enable/disable, and remove a connector
against any of 15 real categories; assign and rotate a credential. Not
a curated list of named integrations (no dedicated Ansible/Redfish/
Kubernetes entity exists in the routed backend) — `connectorType` is
honest free text. See the developer guide for the real, but entirely
unrouted, Ansible/Kubernetes-specific service found in a *different*
backend service (`configuration-management-service`) that this
feature does not build against.

## Secure configuration UX — IMPLEMENTED (mechanism; one real backend gap defended against)

API keys and connector credentials are never leaked by this backend
(the raw values are either shown exactly once or never returned at
all). Notification channel config is the one exception — the backend
itself echoes it back unmasked — this frontend applies its own
presentation-layer masking heuristic there (Prompt 011's precedent)
since the backend provides none.

## Validation — IMPLEMENTED (mirrors real backend mutation semantics, not invented rules)

Every form respects its real backend's mutation semantics: a
genuinely-partial `PATCH` sends only what changed; a full-replace
`PUT` always resends the complete, last-known object (never a diff),
including every opaque policy/preference blob unchanged, since the
backend resets anything omitted to its schema default. See the
developer guide's "Why PATCH, never PUT applies inconsistently here"
for the per-route breakdown.

## Concurrency handling — DOCUMENTED, not implementable as asked

§22 asks for optimistic-locking conflict detection ("This
configuration changed elsewhere..."). Confirmed by direct source
inspection: every settings/config mutation across every service in
this feature bypasses the one real optimistic-locking mechanism this
platform's own framework provides (`BaseRepository.update` with
`expected_version`), and no request schema exposes a `version` field
to the client at all. There is no signal to detect a conflict with —
building the suggested UX would mean fabricating one. Documented as
the single largest gap this prompt found, not implemented around.

## Accessibility — IMPLEMENTED (foundation, one new reused pattern)

Every field uses the existing `FormField` label/description/error
composition; every toggle is a real `Switch`/`Checkbox`. This prompt's
one new structural pattern — System's tabbed observability panel —
reuses the existing accessible `Tabs` component rather than
hand-rolling tablist markup again.

## Responsive design — IMPLEMENTED (foundation)

Built entirely on the existing `SettingsLayout` (Prompt 001) —
sidebar + content on desktop, the same layout's own responsive
behavior on narrower viewports. No second settings shell was created.

## Maintainability — IMPLEMENTED (foundation)

`Page → Hooks → API module → apiClient → real V1 endpoint` (one API
module and one hook file per backend service), strict TypeScript, no
`any`, and query keys that invalidate cleanly after every mutation —
the same architecture every prior feature this session established.

## AI settings — UNAVAILABLE (documented, not implemented)

`ai-assistant-service` exposes no preference or settings endpoint of
any kind (confirmed absent from every router in that service). Shown
as an explicit, honest empty state rather than silently omitting the
nav item.

## Tenant/organization provisioning (`/admin/tenants*`) — UNAVAILABLE here by design, not by omission

Real and RBAC-enforced, but cross-organization operator tooling that
depends on an organization already existing in a database this same
service provides no route to populate — see the developer guide.
Deliberately excluded from a per-organization Settings page.

## Change password (with current password) — UNAVAILABLE (documented, not implemented)

No authenticated "change password" route exists anywhere in
`authentication-service` — confirmed absent. Only the anonymous,
email-token-based forgot/reset-password flow is real; that's what
**Security → Password** offers.

## Configuration-management-service capabilities — UNAVAILABLE (real backend logic, zero HTTP route, wrong shape for this page anyway)

Environment/variable/policy/baseline/approval/change-set/TOSCA/
Ansible/Kubernetes management all have full service-layer
implementations in `configuration-management-service` with zero route
reaching any of them. Even if routed, their actual purpose (managed-
asset configuration profiles) doesn't map onto this prompt's own
Settings IA — see the developer guide.

See `../backend-v1-integration-limitations.md` for the full,
cross-prompt list with source citations.
