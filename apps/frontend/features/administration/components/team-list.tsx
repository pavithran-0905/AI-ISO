"use client";

import { Pencil, Trash2 } from "lucide-react";
import { useState } from "react";

import { ApiRequestError } from "@/api/client";
import { Card, CardContent } from "@/components/data-display/card";
import { Dialog } from "@/components/overlays/dialog";
import { Button } from "@/components/ui/button";
import { IconButton } from "@/components/ui/icon-button";
import { useRemoveTeam } from "@/features/administration/hooks/use-teams";
import type { Team } from "@/features/administration/types";
import { toast } from "@/state/toast-store";

/** No team-members endpoint exists anywhere in this backend
 * (confirmed absent) — a team is shown as identity/metadata only,
 * never a member roster this frontend can't actually fetch. */
export function TeamList({ teams, onEdit }: { teams: Team[]; onEdit: (team: Team) => void }) {
  const removeTeam = useRemoveTeam();
  const [confirmDelete, setConfirmDelete] = useState<Team | null>(null);

  async function handleDelete() {
    if (!confirmDelete) return;
    try {
      await removeTeam.mutateAsync(confirmDelete.id);
      toast.success("Team removed");
      setConfirmDelete(null);
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not remove team", message);
    }
  }

  return (
    <>
      <ul className="flex flex-col gap-2">
        {teams.map((team) => (
          <li key={team.id}>
            <Card>
              <CardContent className="flex items-center justify-between gap-3 p-4">
                <div>
                  <p className="text-sm font-medium">
                    {team.name} {team.code && <span className="text-muted-foreground font-mono text-xs">({team.code})</span>}
                  </p>
                  {team.description && <p className="text-muted-foreground text-xs">{team.description}</p>}
                </div>
                <div className="flex items-center gap-1">
                  <IconButton icon={Pencil} aria-label={`Edit ${team.name}`} variant="ghost" onClick={() => onEdit(team)} />
                  <IconButton icon={Trash2} aria-label={`Remove ${team.name}`} variant="ghost" onClick={() => setConfirmDelete(team)} />
                </div>
              </CardContent>
            </Card>
          </li>
        ))}
      </ul>

      <Dialog
        open={confirmDelete !== null}
        onClose={() => setConfirmDelete(null)}
        title={`Remove ${confirmDelete?.name ?? "this team"}?`}
        description="This removes the team's record. AI-IOS has no team-membership endpoint, so there's no membership to reassign first."
        footer={
          <>
            <Button variant="outline" onClick={() => setConfirmDelete(null)}>
              Cancel
            </Button>
            <Button variant="danger" onClick={() => void handleDelete()} loading={removeTeam.isPending}>
              Remove team
            </Button>
          </>
        }
      />
    </>
  );
}
