"use client";

import { Trash2 } from "lucide-react";
import { useState } from "react";

import { ApiRequestError } from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/data-display/card";
import { Alert } from "@/components/feedback/alert";
import { EmptyState } from "@/components/feedback/empty-state";
import { Button } from "@/components/ui/button";
import { IconButton } from "@/components/ui/icon-button";
import { Dialog } from "@/components/overlays/dialog";
import { FormField } from "@/components/forms/form-field";
import { Input } from "@/components/forms/input";
import { Select } from "@/components/forms/select";
import { useSession } from "@/auth/session";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useAddProjectMember, useProjectMembers, useRemoveProjectMember, useUpdateProjectMemberRole } from "@/features/settings/hooks/use-project-members";
import { PROJECT_ROLE_CODES, type ProjectMember, type ProjectRoleCodeValue } from "@/features/settings/types";
import { toast } from "@/state/toast-store";

/**
 * `GET/POST /projects/{id}/members`, `DELETE .../{userId}`,
 * `PUT .../{userId}/roles` — real project membership and role
 * assignment (Prompt 014's own research; surfaced here rather than in
 * Administration since it's fundamentally "configure this project,"
 * not "manage this user's identity" — see the developer guide's "Why
 * project membership lives in Settings" section, and §47's own "keep
 * responsibilities clear" instruction).
 *
 * **No self-lockout protection exists on the backend** (confirmed:
 * neither `remove` nor `update_role` has any last-owner/last-admin/
 * self-removal guard) — this component blocks removing or demoting
 * the project's sole Owner from the UI, since nothing else will.
 * Setting a member's role to `owner` triggers a full **ownership
 * transfer** server-side (the previous owner is demoted to
 * administrator) — shown with its own distinct confirmation, never a
 * plain role-change dropdown.
 */
export function ProjectMembersSection({ projectId, canEdit }: { projectId: string; canEdit: boolean }) {
  const { userId: currentUserId } = useSession();
  const membersQuery = useProjectMembers(projectId);
  const addMember = useAddProjectMember(projectId);
  const updateRole = useUpdateProjectMemberRole(projectId);
  const removeMember = useRemoveProjectMember(projectId);

  const [addOpen, setAddOpen] = useState(false);
  const [newUserId, setNewUserId] = useState("");
  const [newRoleCode, setNewRoleCode] = useState<ProjectRoleCodeValue>("developer");
  const [transferTarget, setTransferTarget] = useState<ProjectMember | null>(null);
  const [removeTarget, setRemoveTarget] = useState<ProjectMember | null>(null);

  const owners = (membersQuery.data ?? []).filter((member) => member.roleCode === "owner");
  const isSoleOwner = (member: ProjectMember) => member.roleCode === "owner" && owners.length === 1;

  async function handleAdd(event: React.FormEvent) {
    event.preventDefault();
    try {
      await addMember.mutateAsync({ userId: newUserId, roleCode: newRoleCode });
      toast.success("Member added");
      setAddOpen(false);
      setNewUserId("");
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not add member", message);
    }
  }

  async function handleRoleChange(member: ProjectMember, roleCode: ProjectRoleCodeValue) {
    if (roleCode === "owner") {
      setTransferTarget(member);
      return;
    }
    if (isSoleOwner(member)) {
      toast.danger("Can't change this role", "This is the project's only Owner — promote someone else to Owner first.");
      return;
    }
    try {
      await updateRole.mutateAsync({ userId: member.userId, input: { roleCode } });
      toast.success("Role updated");
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not update role", message);
    }
  }

  async function confirmTransfer() {
    if (!transferTarget) return;
    try {
      await updateRole.mutateAsync({ userId: transferTarget.userId, input: { roleCode: "owner" } });
      toast.success("Ownership transferred", "The previous Owner is now an Administrator.");
      setTransferTarget(null);
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not transfer ownership", message);
    }
  }

  async function confirmRemove() {
    if (!removeTarget) return;
    try {
      await removeMember.mutateAsync(removeTarget.userId);
      toast.success("Member removed");
      setRemoveTarget(null);
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not remove member", message);
    }
  }

  function requestRemove(member: ProjectMember) {
    if (isSoleOwner(member)) {
      toast.danger("Can't remove this member", "This is the project's only Owner — transfer ownership first.");
      return;
    }
    setRemoveTarget(member);
  }

  if (!canEdit) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Members</CardTitle>
          <CardDescription>Your role doesn&apos;t allow managing membership.</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <div>
          <CardTitle>Members</CardTitle>
          <CardDescription>Role codes come from a fixed, real 8-value system catalog — no endpoint lists custom roles.</CardDescription>
        </div>
        <Button variant="outline" onClick={() => setAddOpen(true)}>
          Add member
        </Button>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <Alert tone="warning" title="No self-lockout protection on the backend">
          Removing or demoting a project&apos;s only Owner is not blocked by this backend at all — this page blocks it itself
          instead.
        </Alert>

        <SectionState isLoading={membersQuery.isLoading} isError={membersQuery.isError} error={membersQuery.error} onRetry={() => membersQuery.refetch()}>
          {membersQuery.data &&
            (membersQuery.data.length === 0 ? (
              <EmptyState title="No members" description="Add one above." />
            ) : (
              <ul className="flex flex-col gap-2">
                {membersQuery.data.map((member) => {
                  const isSelf = member.userId === currentUserId;
                  return (
                    <li key={member.id} className="flex items-center justify-between gap-3 text-sm">
                      <div>
                        <p className="font-medium">
                          {member.userId}
                          {isSelf && <span className="text-muted-foreground ml-2 text-xs">(you)</span>}
                        </p>
                        <p className="text-muted-foreground text-xs">{member.status}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <Select
                          aria-label={`Role for ${member.userId}`}
                          value={member.roleCode}
                          onChange={(event) => void handleRoleChange(member, event.target.value as ProjectRoleCodeValue)}
                          className="w-44"
                        >
                          {PROJECT_ROLE_CODES.map((code) => (
                            <option key={code} value={code}>
                              {code}
                            </option>
                          ))}
                        </Select>
                        <IconButton
                          icon={Trash2}
                          aria-label={`Remove ${member.userId}`}
                          variant="ghost"
                          onClick={() => requestRemove(member)}
                        />
                      </div>
                    </li>
                  );
                })}
              </ul>
            ))}
        </SectionState>
      </CardContent>

      <Dialog open={addOpen} onClose={() => setAddOpen(false)} title="Add a member">
        <form onSubmit={handleAdd} className="flex flex-col gap-4">
          <FormField label="User ID" required description="Raw id — no user picker exists here yet.">
            {(fieldProps) => <Input {...fieldProps} value={newUserId} onChange={(event) => setNewUserId(event.target.value)} required className="font-mono" />}
          </FormField>
          <FormField label="Role" required>
            {(fieldProps) => (
              <Select {...fieldProps} value={newRoleCode} onChange={(event) => setNewRoleCode(event.target.value as ProjectRoleCodeValue)}>
                {PROJECT_ROLE_CODES.filter((code) => code !== "owner").map((code) => (
                  <option key={code} value={code}>
                    {code}
                  </option>
                ))}
              </Select>
            )}
          </FormField>
          <Button type="submit" loading={addMember.isPending} disabled={!newUserId} className="w-fit">
            Add member
          </Button>
        </form>
      </Dialog>

      <Dialog
        open={transferTarget !== null}
        onClose={() => setTransferTarget(null)}
        title="Transfer project ownership?"
        description="Setting this member to Owner is a full ownership transfer — the current Owner is automatically demoted to Administrator. This is not a plain role change."
        footer={
          <>
            <Button variant="outline" onClick={() => setTransferTarget(null)}>
              Cancel
            </Button>
            <Button variant="danger" onClick={() => void confirmTransfer()} loading={updateRole.isPending}>
              Transfer ownership
            </Button>
          </>
        }
      />

      <Dialog
        open={removeTarget !== null}
        onClose={() => setRemoveTarget(null)}
        title={`Remove this member?`}
        description="This immediately revokes their access to the project. The backend performs a hard delete of the membership record."
        footer={
          <>
            <Button variant="outline" onClick={() => setRemoveTarget(null)}>
              Cancel
            </Button>
            <Button variant="danger" onClick={() => void confirmRemove()} loading={removeMember.isPending}>
              Remove member
            </Button>
          </>
        }
      />
    </Card>
  );
}
