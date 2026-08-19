"use client";

import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { ApiRequestError } from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/data-display/card";
import { EmptyState } from "@/components/feedback/empty-state";
import { Button } from "@/components/ui/button";
import { IconButton } from "@/components/ui/icon-button";
import { Dialog } from "@/components/overlays/dialog";
import { FormField } from "@/components/forms/form-field";
import { Input } from "@/components/forms/input";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useApiKeys, useCreateApiKey, useRevokeApiKey } from "@/features/settings/hooks/use-security";
import type { ApiKeyCreated } from "@/features/settings/types";
import { toast } from "@/state/toast-store";

/**
 * `POST/GET/DELETE /auth/apikeys` — the raw key is returned exactly
 * once, from the create response, and never retrievable again
 * (confirmed: `GET`'s own response never includes it) — shown in a
 * one-time reveal dialog the user must explicitly close, never logged
 * or placed in a URL.
 */
export function ApiKeysSection() {
  const apiKeysQuery = useApiKeys();
  const createApiKey = useCreateApiKey();
  const revokeApiKey = useRevokeApiKey();
  const [createOpen, setCreateOpen] = useState(false);
  const [name, setName] = useState("");
  const [createdKey, setCreatedKey] = useState<ApiKeyCreated | null>(null);

  async function handleCreate(event: React.FormEvent) {
    event.preventDefault();
    try {
      const created = await createApiKey.mutateAsync({ name, scopes: [] });
      setCreatedKey(created);
      setCreateOpen(false);
      setName("");
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not create API key", message);
    }
  }

  async function handleRevoke(apiKeyId: string) {
    try {
      await revokeApiKey.mutateAsync(apiKeyId);
      toast.success("API key revoked");
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not revoke API key", message);
    }
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <div>
          <CardTitle>API keys</CardTitle>
          <CardDescription>Keys for scripts and integrations to call the AI-IOS API as you.</CardDescription>
        </div>
        <IconButton icon={Plus} aria-label="Create API key" variant="outline" onClick={() => setCreateOpen(true)} />
      </CardHeader>
      <CardContent>
        <SectionState isLoading={apiKeysQuery.isLoading} isError={apiKeysQuery.isError} error={apiKeysQuery.error} onRetry={() => apiKeysQuery.refetch()}>
          {apiKeysQuery.data &&
            (apiKeysQuery.data.length === 0 ? (
              <EmptyState title="No API keys" description="Create one to authenticate a script or integration as you." />
            ) : (
              <ul className="flex flex-col gap-2">
                {apiKeysQuery.data.map((key) => (
                  <li key={key.id} className="flex items-center justify-between gap-3 text-sm">
                    <div>
                      <p className="font-medium">
                        {key.name} <span className="text-muted-foreground font-mono text-xs">{key.keyPrefix}…</span>
                      </p>
                      <p className="text-muted-foreground text-xs">
                        {key.revokedAt ? "Revoked" : key.lastUsedAt ? `Last used ${new Date(key.lastUsedAt).toLocaleDateString()}` : "Never used"}
                      </p>
                    </div>
                    {!key.revokedAt && (
                      <IconButton
                        icon={Trash2}
                        aria-label={`Revoke ${key.name}`}
                        variant="ghost"
                        onClick={() => void handleRevoke(key.id)}
                        loading={revokeApiKey.isPending}
                      />
                    )}
                  </li>
                ))}
              </ul>
            ))}
        </SectionState>
      </CardContent>

      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} title="Create API key">
        <form onSubmit={handleCreate} className="flex flex-col gap-4">
          <FormField label="Name" required>
            {(fieldProps) => <Input {...fieldProps} value={name} onChange={(event) => setName(event.target.value)} required />}
          </FormField>
          <Button type="submit" loading={createApiKey.isPending} disabled={!name} className="w-fit">
            Create key
          </Button>
        </form>
      </Dialog>

      <Dialog open={createdKey !== null} onClose={() => setCreatedKey(null)} title="API key created">
        <div className="flex flex-col gap-3">
          <p className="text-sm">Copy this key now — it won&apos;t be shown again.</p>
          <p className="bg-muted rounded-md p-2 font-mono text-xs break-all">{createdKey?.rawKey}</p>
          <Button
            onClick={() => {
              void navigator.clipboard.writeText(createdKey?.rawKey ?? "");
              toast.info("Key copied");
            }}
            className="w-fit"
          >
            Copy key
          </Button>
        </div>
      </Dialog>
    </Card>
  );
}
