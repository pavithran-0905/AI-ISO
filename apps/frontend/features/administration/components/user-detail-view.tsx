"use client";

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/data-display/card";
import { StatusIndicator } from "@/components/data-display/status-indicator";
import { USER_STATUS_TO_STATE } from "@/features/administration/lib/status-maps";
import { RoleAssignmentSection } from "@/features/administration/components/role-assignment-section";
import { UserNotesSection } from "@/features/administration/components/user-notes-section";
import { UserStatusActions } from "@/features/administration/components/user-status-actions";
import type { UserDetail } from "@/features/administration/types";

/**
 * §11: Identity → Access → Membership → Activity, per the prompt's own
 * hierarchy — except Access/Membership/Activity for *another* user are
 * confirmed unavailable (see the developer guide): no endpoint
 * correlates a user to their organization/project/team memberships or
 * role assignments, and `/users/activity` only ever returns the
 * caller's own activity, never an arbitrary target user's. Shown as an
 * explicit, honest gap rather than fabricated or silently omitted.
 */
export function UserDetailView({ user }: { user: UserDetail }) {
  return (
    <div className="flex flex-col gap-6">
      <IdentitySection user={user} />
      <UserStatusActions user={user} />
      <AccessMembershipGap />
      <RoleAssignmentSection userId={user.id} />
      <UserNotesSection userId={user.id} />
    </div>
  );
}

function IdentitySection({ user }: { user: UserDetail }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Identity</CardTitle>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
          <Field label="Username" value={user.username} mono />
          <Field label="Email" value={user.email} />
          <Field label="Display name" value={user.displayName} />
          <Field label="First name" value={user.firstName} />
          <Field label="Middle name" value={user.middleName} />
          <Field label="Last name" value={user.lastName} />
          <Field label="Phone" value={user.phoneNumber} />
          <Field label="Timezone" value={user.timezone} />
          <Field label="Language" value={user.language} />
          <Field label="Locale" value={user.locale} />
          <div className="flex flex-col gap-0.5">
            <dt className="text-muted-foreground text-xs">Status</dt>
            <dd>
              <StatusIndicator state={USER_STATUS_TO_STATE[user.status]} label={user.status} />
            </dd>
          </div>
          <Field label="Last login" value={user.lastLogin ? new Date(user.lastLogin).toLocaleString() : null} />
          <Field label="Created" value={new Date(user.createdAt).toLocaleString()} />
        </dl>
      </CardContent>
    </Card>
  );
}

function AccessMembershipGap() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Access &amp; membership</CardTitle>
        <CardDescription>Not available.</CardDescription>
      </CardHeader>
      <CardContent className="text-muted-foreground text-sm">
        No endpoint anywhere in AI-IOS correlates this user to an organization membership, a project membership, a team,
        or their existing role assignments — confirmed by direct source inspection across four services. This isn&apos;t a
        loading state or a permission restriction; the data genuinely doesn&apos;t exist to fetch. See the developer guide
        for the full breakdown.
      </CardContent>
    </Card>
  );
}

function Field({ label, value, mono = false }: { label: string; value: string | null; mono?: boolean }) {
  if (!value) return null;
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-muted-foreground text-xs">{label}</dt>
      <dd className={mono ? "font-mono text-xs" : "text-sm"}>{value}</dd>
    </div>
  );
}
