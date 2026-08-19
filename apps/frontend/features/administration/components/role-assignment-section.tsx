"use client";

import { useState } from "react";

import { ApiRequestError } from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/data-display/card";
import { Alert } from "@/components/feedback/alert";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/overlays/dialog";
import { FormField } from "@/components/forms/form-field";
import { Select } from "@/components/forms/select";
import { useAssignRole, useRbacRoles } from "@/features/administration/hooks/use-rbac";
import type { AssignRoleInput } from "@/features/administration/types";
import { toast } from "@/state/toast-store";

/**
 * `POST /users/{id}/roles` (`rbac-service`) — real §20 "Select User →
 * Select Role → Confirm → Backend Confirmation" workflow, real HTTP
 * 201, real persisted row. **Confirmed, by direct cross-service
 * inspection, to have zero effect on what this user can actually do
 * anywhere else in AI-IOS** — no other service ever reads
 * `rbac-service`'s tables at authorization time; every service checks
 * the caller's own JWT `role` claim locally instead. The warning below
 * is not optional decoration — assigning a role here without reading
 * it would leave an administrator believing they've granted access
 * they haven't.
 */
export function RoleAssignmentSection({ userId }: { userId: string }) {
  const rolesQuery = useRbacRoles();
  const assignRole = useAssignRole(userId);
  const [open, setOpen] = useState(false);
  const [roleId, setRoleId] = useState("");
  const [scopeType, setScopeType] = useState<AssignRoleInput["scopeType"]>("global");

  async function handleAssign(event: React.FormEvent) {
    event.preventDefault();
    try {
      await assignRole.mutateAsync({ roleId, scopeType });
      toast.success("Role assignment recorded", "This has no live effect on this user's actual access — see the note on this page.");
      setOpen(false);
      setRoleId("");
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not assign role", message);
    }
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <div>
          <CardTitle>Role assignment</CardTitle>
          <CardDescription>rbac-service&apos;s own role catalog.</CardDescription>
        </div>
        <Button variant="outline" onClick={() => setOpen(true)}>
          Assign a role
        </Button>
      </CardHeader>
      <CardContent>
        <Alert tone="danger" title="This does not grant real access">
          rbac-service&apos;s role/permission tables are not consulted by any other AI-IOS service when deciding what a
          user can do — confirmed by direct source inspection. Assigning a role here creates a real, persisted record in
          rbac-service only; it does not change this user&apos;s actual permissions anywhere in AI-IOS today. There is also
          no way to view this user&apos;s existing assignments — no such endpoint exists.
        </Alert>
      </CardContent>

      <Dialog open={open} onClose={() => setOpen(false)} title="Assign a role">
        <form onSubmit={handleAssign} className="flex flex-col gap-4">
          <FormField label="Role" required>
            {(fieldProps) => (
              <Select {...fieldProps} value={roleId} onChange={(event) => setRoleId(event.target.value)} required>
                <option value="">Select a role…</option>
                {(rolesQuery.data ?? []).map((role) => (
                  <option key={role.id} value={role.id}>
                    {role.name} ({role.code})
                  </option>
                ))}
              </Select>
            )}
          </FormField>
          <FormField label="Scope" required>
            {(fieldProps) => (
              <Select {...fieldProps} value={scopeType} onChange={(event) => setScopeType(event.target.value as AssignRoleInput["scopeType"])}>
                <option value="global">Global</option>
                <option value="organization">Organization</option>
                <option value="project">Project</option>
              </Select>
            )}
          </FormField>
          <Button type="submit" loading={assignRole.isPending} disabled={!roleId} className="w-fit">
            Record assignment
          </Button>
        </form>
      </Dialog>
    </Card>
  );
}
