"use client";

import { useState } from "react";

import { ApiRequestError } from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/data-display/card";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/overlays/dialog";
import { Label } from "@/components/forms/label";
import { Select } from "@/components/forms/select";
import { useSession } from "@/auth/session";
import { usePatchUser, useRemoveUser } from "@/features/administration/hooks/use-users";
import { USER_STATUSES, type UserDetail, type UserStatusValue } from "@/features/administration/types";
import { toast } from "@/state/toast-store";

/** A status other than these leaves an account able to sign in and
 * act — used only for the self-lockout warning below, not to
 * pre-validate legal transitions (the real transition table isn't
 * exposed by any endpoint — see the type's own docstring; an illegal
 * transition is simply rejected by the backend's own real 409). */
const RESTRICTIVE_STATUSES = new Set<UserStatusValue>(["inactive", "locked", "disabled", "suspended", "deleted", "archived"]);

/**
 * `PATCH /users/{id}` status transitions (real, backend-validated
 * lifecycle state machine) and `DELETE /users/{id}` (a soft delete via
 * `is_active`, not a status transition — see `usersApi.remove`'s own
 * docstring). §14 self-lockout protection: the backend has **no**
 * self-lockout guard of any kind (it's the same "no permission check
 * at all" gap covering every route in this service) — this component
 * adds its own warning when the viewed user is the caller themself and
 * the chosen status/action would leave them unable to act, since
 * nothing else in the platform will stop it.
 */
export function UserStatusActions({ user }: { user: UserDetail }) {
  const { userId: currentUserId } = useSession();
  const patchUser = usePatchUser(user.id);
  const removeUser = useRemoveUser();
  const [pendingStatus, setPendingStatus] = useState<UserStatusValue | "">("");
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);
  const isSelf = currentUserId === user.id;

  async function handleStatusChange(event: React.FormEvent) {
    event.preventDefault();
    if (!pendingStatus) return;
    try {
      await patchUser.mutateAsync({ status: pendingStatus });
      toast.success(`Status changed to ${pendingStatus}`);
      setPendingStatus("");
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not change status", message);
    }
  }

  async function handleDelete() {
    try {
      await removeUser.mutateAsync(user.id);
      toast.success("User removed");
      setConfirmDeleteOpen(false);
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not remove user", message);
    }
  }

  const wouldSelfLock = isSelf && pendingStatus !== "" && RESTRICTIVE_STATUSES.has(pendingStatus);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Status</CardTitle>
        <CardDescription>
          Backend-validated: an unsupported transition (e.g. reactivating a deleted account) is rejected with a real error,
          not pre-checked here.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {isSelf && (
          <p className="text-warning text-xs">You are viewing your own account. Changing your own status may sign you out.</p>
        )}

        <form onSubmit={handleStatusChange} className="flex items-end gap-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="status-select">Change status</Label>
            <Select id="status-select" value={pendingStatus} onChange={(event) => setPendingStatus(event.target.value as UserStatusValue)} className="w-44">
              <option value="">Select a status…</option>
              {USER_STATUSES.map((status) => (
                <option key={status} value={status} disabled={status === user.status}>
                  {status}
                </option>
              ))}
            </Select>
          </div>
          <Button type="submit" disabled={!pendingStatus} loading={patchUser.isPending} variant={wouldSelfLock ? "danger" : "primary"}>
            {wouldSelfLock ? "Change anyway" : "Apply"}
          </Button>
        </form>
        {wouldSelfLock && <p className="text-danger text-xs">This would restrict your own access — the backend won&apos;t stop you.</p>}

        <Button variant="danger" onClick={() => setConfirmDeleteOpen(true)} className="w-fit">
          Remove user
        </Button>
      </CardContent>

      <Dialog
        open={confirmDeleteOpen}
        onClose={() => setConfirmDeleteOpen(false)}
        title={`Remove ${user.displayName ?? user.username}?`}
        description={
          isSelf
            ? "This is your own account. Removing it will soft-delete it (is_active=false) and it will 404 from every other route in this service, including your own session's future calls."
            : "This soft-deletes the account (is_active=false) — it stops appearing in lists and detail lookups, but the row isn't hard-deleted."
        }
        footer={
          <>
            <Button variant="outline" onClick={() => setConfirmDeleteOpen(false)}>
              Cancel
            </Button>
            <Button variant="danger" onClick={() => void handleDelete()} loading={removeUser.isPending}>
              Remove user
            </Button>
          </>
        }
      />
    </Card>
  );
}
