"use client";

import { useState } from "react";

import { ApiRequestError } from "@/api/client";
import { Dialog } from "@/components/overlays/dialog";
import { Button } from "@/components/ui/button";
import { FormField } from "@/components/forms/form-field";
import { Input } from "@/components/forms/input";
import { Textarea } from "@/components/forms/textarea";
import { useCreateTeam, useUpdateTeam } from "@/features/administration/hooks/use-teams";
import type { Team } from "@/features/administration/types";
import { toast } from "@/state/toast-store";

/** `POST /organizations/{id}/teams` for create, `PUT /teams/{id}` for
 * edit — one dialog handles both, matching the create-vs-edit-by-prop
 * pattern already established for connector dialogs (Prompt 013).
 * `key`ed by the target team so the form's local state resets to a
 * clean slate whenever a different team (or "create") is opened,
 * instead of an effect syncing it after the fact. */
export function TeamFormDialog({
  organizationId,
  team,
  open,
  onClose,
}: {
  organizationId: string;
  team: Team | null;
  open: boolean;
  onClose: () => void;
}) {
  return (
    <Dialog open={open} onClose={onClose} title={team ? `Edit ${team.name}` : "Create a team"}>
      <TeamForm key={team?.id ?? "create"} organizationId={organizationId} team={team} onClose={onClose} />
    </Dialog>
  );
}

function TeamForm({ organizationId, team, onClose }: { organizationId: string; team: Team | null; onClose: () => void }) {
  const createTeam = useCreateTeam();
  const updateTeam = useUpdateTeam();
  const [name, setName] = useState(team?.name ?? "");
  const [code, setCode] = useState(team?.code ?? "");
  const [description, setDescription] = useState(team?.description ?? "");

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    try {
      if (team) {
        await updateTeam.mutateAsync({ teamId: team.id, input: { name, code: code || undefined, description: description || undefined } });
        toast.success("Team updated");
      } else {
        await createTeam.mutateAsync({ organizationId, name, code: code || undefined, description: description || undefined });
        toast.success("Team created");
      }
      onClose();
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger(team ? "Could not update team" : "Could not create team", message);
    }
  }

  const isPending = createTeam.isPending || updateTeam.isPending;

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <FormField label="Name" required>
        {(fieldProps) => <Input {...fieldProps} value={name} onChange={(event) => setName(event.target.value)} required />}
      </FormField>
      <FormField label="Code">
        {(fieldProps) => <Input {...fieldProps} value={code} onChange={(event) => setCode(event.target.value)} />}
      </FormField>
      <FormField label="Description">
        {(fieldProps) => <Textarea {...fieldProps} value={description} onChange={(event) => setDescription(event.target.value)} />}
      </FormField>
      <Button type="submit" loading={isPending} disabled={!name} className="w-fit">
        {team ? "Save changes" : "Create team"}
      </Button>
    </form>
  );
}
