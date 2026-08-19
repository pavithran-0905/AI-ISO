"use client";

import { LogOut } from "lucide-react";

import { ApiRequestError } from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/data-display/card";
import { EmptyState } from "@/components/feedback/empty-state";
import { Button } from "@/components/ui/button";
import { IconButton } from "@/components/ui/icon-button";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useSessions, useTerminateAllSessions, useTerminateSession } from "@/features/settings/hooks/use-security";
import { toast } from "@/state/toast-store";

/** `GET/DELETE /auth/sessions` — every active session for the caller. */
export function SessionsSection() {
  const sessionsQuery = useSessions();
  const terminateSession = useTerminateSession();
  const terminateAll = useTerminateAllSessions();

  async function handleTerminate(sessionDbId: string) {
    try {
      await terminateSession.mutateAsync(sessionDbId);
      toast.success("Session terminated");
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not terminate session", message);
    }
  }

  async function handleTerminateAll() {
    try {
      const count = await terminateAll.mutateAsync();
      toast.success(`${count} session${count === 1 ? "" : "s"} terminated`);
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not terminate sessions", message);
    }
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <div>
          <CardTitle>Active sessions</CardTitle>
          <CardDescription>Everywhere you&apos;re currently signed in.</CardDescription>
        </div>
        {sessionsQuery.data && sessionsQuery.data.length > 1 && (
          <Button variant="outline" onClick={() => void handleTerminateAll()} loading={terminateAll.isPending}>
            Sign out everywhere
          </Button>
        )}
      </CardHeader>
      <CardContent>
        <SectionState isLoading={sessionsQuery.isLoading} isError={sessionsQuery.isError} error={sessionsQuery.error} onRetry={() => sessionsQuery.refetch()}>
          {sessionsQuery.data &&
            (sessionsQuery.data.length === 0 ? (
              <EmptyState title="No active sessions" description="Nothing is currently signed in as you." />
            ) : (
              <ul className="flex flex-col gap-2">
                {sessionsQuery.data.map((session) => (
                  <li key={session.id} className="flex items-center justify-between gap-3 text-sm">
                    <div>
                      <p className="font-medium">{session.userAgent ?? "Unknown device"}</p>
                      <p className="text-muted-foreground text-xs">
                        {session.ipAddress ?? "Unknown IP"} · Active {new Date(session.lastActiveAt).toLocaleString()}
                      </p>
                    </div>
                    <IconButton
                      icon={LogOut}
                      aria-label="Terminate session"
                      variant="ghost"
                      onClick={() => void handleTerminate(session.id)}
                      loading={terminateSession.isPending}
                    />
                  </li>
                ))}
              </ul>
            ))}
        </SectionState>
      </CardContent>
    </Card>
  );
}
