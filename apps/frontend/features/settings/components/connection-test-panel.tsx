"use client";

import { ApiRequestError } from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/data-display/card";
import { StatusBadge } from "@/components/feedback/status-badge";
import { Button } from "@/components/ui/button";
import { useTestConnection } from "@/features/settings/hooks/use-integrations";
import { toast } from "@/state/toast-store";

/**
 * `POST /integrations/connectors/{id}/test` (§13) — never claims
 * success before the backend confirms it; the UI's own "Testing" state
 * is just the mutation's pending state, not a client-guessed outcome.
 * A `success` result with no `latencyMs` means a structural check only
 * (config+credential presence, no real outbound call was made) —
 * shown explicitly rather than implying every success reached the
 * remote system.
 */
export function ConnectionTestPanel({ connectorId }: { connectorId: string }) {
  const testConnection = useTestConnection(connectorId);

  async function handleTest() {
    try {
      const result = await testConnection.mutateAsync();
      if (result.status === "success") {
        toast.success(
          result.latencyMs !== null ? `Connection succeeded (${result.latencyMs}ms)` : "Configuration looks structurally valid",
          result.latencyMs === null ? "No real outbound call was made — only config and credential presence were checked." : undefined,
        );
      } else {
        toast.danger("Connection test failed", result.error ?? "The connector did not report a reason.");
      }
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not run connection test", message);
    }
  }

  const result = testConnection.data;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Test connection</CardTitle>
        <CardDescription>Runs a real check against this connector&apos;s current configuration.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <Button onClick={() => void handleTest()} loading={testConnection.isPending} variant="outline" className="w-fit">
          {testConnection.isPending ? "Testing…" : "Test connection"}
        </Button>
        {result && (
          <div className="flex items-center gap-2 text-sm">
            <StatusBadge tone={result.status === "success" ? "success" : "danger"} label={result.status === "success" ? "Success" : "Failed"} />
            <span className="text-muted-foreground">
              {result.latencyMs !== null ? `${result.latencyMs}ms` : "Structural check only"} · {new Date(result.testedAt).toLocaleString()}
            </span>
          </div>
        )}
        {result?.error && <p className="text-danger text-xs">{result.error}</p>}
      </CardContent>
    </Card>
  );
}
