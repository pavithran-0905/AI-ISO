# Settings

The Enterprise Configuration, Settings & Administration Experience
built in Prompt 013 — the widest backend surface of any single prompt
this session, spanning seven services with no dedicated
"settings-service" (confirmed absent from `services/`).
`docs/frontend/rfi/settings.md` has the implemented-vs-planned split;
`docs/frontend/backend-v1-integration-limitations.md` has the full
gap list with citations.

## Real endpoint inventory, by service

| Service | Real routes this feature consumes | Real, but out of scope |
|---|---|---|
| `user-management-service` | `GET/PUT /users/preferences`, `/users/profile`, `PATCH /users/{id}` (self-edit only) | `/users/settings` (opaque, no scalar fields — see below) |
| `authentication-service` | `POST /auth/mfa/{enable,verify,disable}`, `POST/GET/DELETE /auth/apikeys`, `GET/DELETE /auth/devices`, `GET/DELETE /auth/sessions`, `POST /auth/forgot-password` | — |
| `organization-service` | `GET/PUT /organizations/{id}`, `.../settings`, `.../branding`, `GET .../licenses`, `.../quotas` | — |
| `project-service` | `GET /projects?organization_id=`, `PATCH /projects/{id}`, `GET/PUT /projects/{id}/settings` | — |
| `integration-hub-service` | connector create/list/get/configure/test/enable/disable/remove, credential assign/rotate | versions/upgrade/rollback/deprecate/sync/probe/health-history/marketplace/transformations/flows/events/analytics |
| `notification-center-service` | `GET/PUT /notifications/preferences`, `GET/PUT /notifications/channels/{channel}` | notifications/templates/announcements/subscriptions/dead-letters infrastructure |
| `administration-portal-service` | `GET /admin/dashboard`, `GET/PUT /admin/settings`, `GET/POST/PUT /admin/feature-flags`, `GET/POST /admin/jobs`, `GET /admin/{diagnostics,health,statistics,reports}` | `/admin/tenants*` (deliberately excluded, see below) |

Every route in every one of these seven services was confirmed by
direct source inspection (`app/api/*.py`, `app/schemas/*.py`), not
inferred from a route's name or a docs file.

## Why "PATCH, never PUT" applies inconsistently here — and that's honest, not a bug

Unlike Infrastructure (Prompt 011), where every mutation had a clean
PATCH-safe alternative, this prompt's services split down the middle:

- **Genuinely PATCH-safe**: `PATCH /users/{id}` (user-management-service),
  `PATCH /projects/{id}` (project-service) — both confirmed
  `exclude_unset`, both used here instead of their own service's `PUT`.
- **`PUT`-only, but partial-safe on the backend anyway**:
  `PUT /notifications/preferences` — confirmed the service only applies
  a field when the caller actually sent a non-null value
  (`PreferenceService.update`'s own `if field in _EDITABLE_FIELDS and
  value is not None` check). A real exception to the "PUT resets
  everything" pattern found everywhere else this session.
- **`PUT`-only, and genuinely resets omitted fields to schema
  defaults**: `PUT /users/preferences`, `/users/profile`,
  `/organizations/{id}`, `.../settings`, `.../branding`,
  `/projects/{id}/settings`, `/integrations/connectors/{id}`. Every
  form against one of these always resends the complete, last-fetched
  object — see each component's own docstring for the specific fields
  it round-trips unchanged rather than exposing as editable (always
  the opaque `dict`-shaped fields with no defined sub-schema:
  `dashboardPreferences`, `notificationPreferences`, `accessibility`,
  `customFields`, `passwordPolicy`, `storagePolicy`,
  `notificationPolicy`, `emailTemplates`, `loginScreenBranding`,
  `dashboardBranding`, and most of `ProjectSettings`'s own policy
  fields).

## Why theme stays local, not backend-synced

`/users/preferences` has a real `theme` field. This frontend does
**not** wire it to `useThemeStore` (Prompts 002/006's existing,
already-working, already-everywhere local theme mechanism). §17
explicitly says "do not implement a second theme system" — syncing a
backend copy on top of the local one would create exactly that: two
sources of truth for what the app actually renders, with no clear
resolution order if they disagreed. `theme` is still round-tripped
unchanged on every `/users/preferences` save (never wiped to
`"system"` by an unrelated save), but never read from or written to by
the Display section — `DisplayPreferencesSection` calls
`useThemeStore`/`useTableDensityStore` directly, the same stores every
other page in this app already reads.

## The `/users/{id}` ownership gap

`PATCH /users/{id}` (used for `displayName`/`firstName`/`lastName`/
`phoneNumber`) has **no ownership check on the backend** — confirmed:
`_caller: CurrentUserId` is accepted but never compared to the
`{user_id}` path parameter, so any authenticated caller could in
principle PATCH any other user's record. This frontend only ever calls
it with `userId` from `useSession()` (the real, current caller's own
id) — never a value a user could type into a field — the same
"frontend fixes its own behavior, documents the backend gap, never
exploits it" discipline established for `inventory-service`'s
by-id tenant gap in Prompt 011.

## No optimistic locking, anywhere, despite every table having a `version` column

Confirmed by direct inspection of `OrganizationService.update`,
`OrganizationSettingsService.update`, `OrganizationBrandingService.update`,
`OrganizationLicenseService.update`, `OrganizationQuotaService.update`,
`ProjectService.update`/`.patch`, `ProjectSettingsService.update`,
`UserPreferencesService.update`, `UserSettingsService.update`: every
one of these mutates the SQLAlchemy-tracked entity's attributes
directly and relies on the session's own autoflush/commit, never
calling `BaseRepository.update(entity, expected_version=...)` — the
one method in `shared_core` that actually checks/increments `version`.
No request schema anywhere in this feature even exposes a `version`
field to the client. **Net effect**: two concurrent saves to the same
Organization/Project/Preferences resource silently last-write-wins,
with no conflict ever detected or surfaced. §22's own suggested UX
("This configuration changed elsewhere...") could not be honestly
built — there is no signal to detect the conflict with. Documented,
not fabricated around.

## Why a coarse permission heuristic, not real per-resource checks

Three real, different authorization shapes appear across these seven
services, and the frontend has a live signal for none of them:

1. **Per-organization membership role** (organization-service,
   project-service): `require_admin`/`require_project_admin` check the
   caller's *membership row* in that specific organization/project —
   looked up per-request from the database, not from the JWT. This
   frontend's own `role` claim is platform-wide (and, per the
   documented Prompt 001 gap, frequently `null` regardless).
2. **JWT `roles` array** (administration-portal-service):
   `require_administrator` checks a `roles` array claim against
   `{admin, administrator, platform_admin, super_admin}` — a claim
   shape this platform's own login flow never populates (confirmed:
   `POST /auth/login` issues tokens with no `extra_claims`). Every
   mutation on this page will 403 today, for every session, regardless
   of the frontend's own gating.
3. **No check at all** (user-management-service, authentication-service,
   integration-hub-service, notification-center-service's user
   preferences): any valid JWT suffices.

Given none of these can be verified client-side, every edit control in
Organization/Projects/System is gated by the existing coarse
`isAdministrative` heuristic (`@/permissions/hooks`) as a **UX
convenience only** — hiding a control saves a wasted click and a real
403, it grants no security. The backend remains the sole authority in
every case; a real 403 is always shown as a real error, never papered
over. See each page's own docstring for exactly which heuristic
backs which section.

## Why System is hidden from the nav for non-administrators, even though its `GET` routes don't require it

`administration-portal-service`'s own read routes (`/admin/dashboard`,
`/admin/settings`, `/admin/feature-flags`, `/admin/jobs`,
`/admin/diagnostics`, `/admin/health`, `/admin/statistics`,
`/admin/reports`) require only a valid JWT — confirmed, no role check
on any of them. A viewer could call every one of these directly. This
frontend still hides the **System** nav item entirely for a
non-administrative session (`lib/nav-items.ts`) — a deliberate,
explicit tightening beyond what the backend enforces, since casually
surfacing platform-wide tenant/settings/feature-flag/job data to an
ordinary viewer would violate §5/§7's intent even though today's
backend wouldn't stop it. This is narrowing access, never widening it
beyond what's real — the opposite direction of every fabrication this
session has refused to do.

## Why `/admin/tenants*` was not built here

Real, tested, RBAC-enforced tenant lifecycle management (provision/
transition/soft-delete), FK'd to an organization that must already
exist in `administration-portal-service`'s own database — but that
service provides **no route to create an organization** in its own
database at all (`OrganizationService.create_organization` exists,
never imported by any route). This reads as platform-operator tooling
for provisioning tenants under organizations that already exist by
some other means, not a per-organization "Settings" self-service
concern — excluded by design, not by omission.

## Integrations: a generic connector framework, not named integrations

`integration-hub-service` models 15 real categories
(`ConnectorCategory`) and a free-text `connectorType` — there is no
dedicated "Ansible"/"Redfish"/"Kubernetes" entity anywhere in this
service. `CreateConnectorDialog` reflects this honestly: category is a
real enum dropdown, connector type is free text with examples in its
own description, never a fabricated closed list of "supported
integrations."

**A real Ansible/Kubernetes-specific service exists — in the wrong
service, and completely unrouted.** `configuration-management-service`
has full `ConfigurationAnsibleService`/`ConfigurationKubernetesService`
classes with real validation logic (`app/ansible/validator.py` for
Ansible inventory bundles; real Kubernetes manifest/Helm/Kustomize
validation) — but that entire service's `app/api/` directory has zero
route reaching either one, or ten other fully-implemented capabilities
(environment/variable/policy/baseline/approval/change-set/TOSCA
management, and the service's own audit trail). This service's actual
*routed* purpose is configuration-profile/version/drift/compliance/
GitOps management for managed assets (cross-referenced by an opaque
`managed_asset_id`, not a real FK) — a different, real capability that
doesn't map onto any category in this prompt's own Settings IA (My
Preferences/Organization/Projects/Integrations/Notifications/AI/
System). Nothing here was built against it; it's a plausible future
feature module of its own, not a Settings section.

## Secret handling — three different backend behaviors, one frontend rule

- `authentication-service`'s API keys: the raw key is returned exactly
  once, from the create response, never again (confirmed: `GET`'s own
  response schema has no such field). Shown in a one-time reveal
  dialog, never logged.
- `integration-hub-service`'s credentials: the secret value is **never**
  returned by any route, not even masked — only a `secretRef` pointer.
  Nothing to leak here by construction.
- `notification-center-service`'s channel `config`: the backend
  **echoes it back completely unmasked**, with zero redaction
  (confirmed: `ChannelService.set_config` stores and returns the dict
  verbatim). This is the one place this feature's own frontend-side
  masking heuristic (Prompt 011's `isSensitiveMetadataKey`/
  `maskMetadataValue`, reused in `ConnectorConfigForm`) matters most —
  though `NotificationChannelsSection` edits this specific field as
  raw JSON rather than enumerable rows, so it warns explicitly instead
  of masking row-by-row; `ConnectorConfigForm`'s key/value rows do mask.

## Query/API architecture

`Settings Page → Settings Hooks (features/settings/hooks/*.ts) →
Settings API Module (features/settings/api/*.ts) → apiClient → Backend
V1`, the same layering every prior feature this session used — seven
API modules, seven hook files, one per backend service, never a
component calling `apiClient` directly.

## Form architecture: plain state, not React Hook Form + Zod

`react-hook-form`/`zod` are both real dependencies in `package.json`
(confirmed) — but confirmed unused by any feature built in this
session before this prompt (`grep` across `features/`/`components/`
for `useForm`/`zodResolver` returns nothing). §18 says to prefer them
"only where already established by the frontend foundation" — the
established *practice*, not just the dependency list, is plain
`useState` + manual validation (Infrastructure's `AssetCreateForm`/
`AssetEditForm`, Prompt 011). Introducing RHF+Zod here for the first
time would be a second, competing form architecture the ROLE
instructions explicitly forbid ("Do not create competing
architecture"). Every form in this feature follows the established
plain-`useState` pattern instead.

## Cross-module effects

- `PATCH /users/{id}` (Identity) and `POST/PUT/POST /auth/mfa/*`
  invalidate `["auth", "profile"]` — the exact query key
  `@/auth/session#useSession` reads — so a display-name change or MFA
  status change is reflected immediately in the account menu, without
  a page reload.
- The account menu's pre-existing "Preferences" item (stubbed since
  Prompt 003 with a comment "wired once one does") now navigates to
  `/settings`.
- Theme/density changes apply immediately app-wide via the existing
  stores — no additional wiring needed, since nothing new was
  introduced.

## Accessibility

Every form field uses the existing `FormField` composition (label/
description/error/`aria-describedby`, Prompt 002) rather than
hand-rolled label markup. Toggle affordances use the real `Switch`
(`role="switch"`) for boolean settings and `Checkbox` for multi-select
groups, never a styled `<div>`. The one new structural pattern this
prompt introduces — `SystemObservabilitySection`'s tabbed diagnostics/
statistics/reports — reuses the existing `Tabs` component (real
`role="tablist"`/`"tab"`/`"tabpanel"`, roving tabindex, Home/End)
rather than the ad hoc tablist markup Topology/TopologySection used in
prior prompts.

## Error handling / partial failure

Every section on every page is its own `useQuery` + `SectionState` —
a slow/failed Organization Branding fetch never blocks Identity or
Policy from rendering, and a 403 from a mutation this session's own
research predicts will always fail (System's writes) is shown as a
real, specific error via the same `ApiRequestError`/`toast.danger`
pattern every other feature uses, never silently swallowed or faked
into a success.
