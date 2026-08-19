"use client";

import { Trash2 } from "lucide-react";
import { useState } from "react";

import { ApiRequestError } from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/data-display/card";
import { EmptyState } from "@/components/feedback/empty-state";
import { Button } from "@/components/ui/button";
import { IconButton } from "@/components/ui/icon-button";
import { Textarea } from "@/components/forms/textarea";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useAddUserNote, useRemoveUserNote, useUserNotes } from "@/features/administration/hooks/use-users";
import { toast } from "@/state/toast-store";

/** `POST/GET/DELETE /users/{id}/notes` — the one router in this
 * service that's genuinely, correctly non-self-scoped by design
 * (`author_id` is the calling admin, `{user_id}` in the path is the
 * note's subject). */
export function UserNotesSection({ userId }: { userId: string }) {
  const notesQuery = useUserNotes(userId);
  const addNote = useAddUserNote(userId);
  const removeNote = useRemoveUserNote(userId);
  const [body, setBody] = useState("");

  async function handleAdd(event: React.FormEvent) {
    event.preventDefault();
    try {
      await addNote.mutateAsync(body);
      setBody("");
      toast.success("Note added");
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not add note", message);
    }
  }

  async function handleRemove(noteId: string) {
    try {
      await removeNote.mutateAsync(noteId);
      toast.success("Note removed");
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not remove note", message);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Admin notes</CardTitle>
        <CardDescription>Internal notes about this account, visible to other administrators.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <form onSubmit={handleAdd} className="flex flex-col gap-2">
          <Textarea value={body} onChange={(event) => setBody(event.target.value)} placeholder="Add a note…" aria-label="New note" />
          <Button type="submit" loading={addNote.isPending} disabled={!body} className="w-fit">
            Add note
          </Button>
        </form>

        <SectionState isLoading={notesQuery.isLoading} isError={notesQuery.isError} error={notesQuery.error} onRetry={() => notesQuery.refetch()}>
          {notesQuery.data &&
            (notesQuery.data.length === 0 ? (
              <EmptyState title="No notes yet" description="Notes added here are visible to other administrators." />
            ) : (
              <ul className="flex flex-col gap-2">
                {notesQuery.data.map((note) => (
                  <li key={note.id} className="border-border flex items-start justify-between gap-3 border-t pt-2 text-sm">
                    <div>
                      <p>{note.body}</p>
                      <p className="text-muted-foreground text-xs">{new Date(note.createdAt).toLocaleString()}</p>
                    </div>
                    <IconButton icon={Trash2} aria-label="Remove note" variant="ghost" onClick={() => void handleRemove(note.id)} loading={removeNote.isPending} />
                  </li>
                ))}
              </ul>
            ))}
        </SectionState>
      </CardContent>
    </Card>
  );
}
