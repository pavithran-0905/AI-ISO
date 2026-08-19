"use client";

import { useState } from "react";

import { ApiRequestError } from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/data-display/card";
import { EmptyState } from "@/components/feedback/empty-state";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/overlays/dialog";
import { FormField } from "@/components/forms/form-field";
import { Input } from "@/components/forms/input";
import { Switch } from "@/components/forms/switch";
import { Textarea } from "@/components/forms/textarea";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useNotificationChannels, useSetNotificationChannel } from "@/features/settings/hooks/use-notification-settings";
import { NOTIFICATION_CHANNEL_KINDS, type NotificationChannelKindValue } from "@/features/settings/types";
import { toast } from "@/state/toast-store";

/**
 * `GET/PUT /notifications/channels` — organization-level channel
 * configuration (e.g. a Slack webhook URL), distinct from the
 * per-user preferences above. **Security note**: the backend echoes
 * `config` back completely unmasked (confirmed absent of any
 * redaction) — this editor warns explicitly rather than silently
 * displaying whatever's already stored; a full masked key/value
 * editor (the Prompt 011 `sensitive-metadata.ts` heuristic) wasn't
 * built for this specific field, since `config` here is edited as raw
 * JSON, not enumerable key/value rows. Requires organization
 * Administrator rank on the backend for writes; gated here by the
 * same coarse heuristic as Organization/Projects.
 */
export function NotificationChannelsSection({ organizationId, canEdit }: { organizationId: string; canEdit: boolean }) {
  const channelsQuery = useNotificationChannels(organizationId);
  const setChannel = useSetNotificationChannel(organizationId);
  const [editingChannel, setEditingChannel] = useState<NotificationChannelKindValue | null>(null);
  const [enabled, setEnabled] = useState(true);
  const [configText, setConfigText] = useState("{}");
  const [description, setDescription] = useState("");

  function openEditor(channel: NotificationChannelKindValue, currentEnabled: boolean, currentConfig: Record<string, unknown>, currentDescription: string) {
    setEditingChannel(channel);
    setEnabled(currentEnabled);
    setConfigText(JSON.stringify(currentConfig, null, 2));
    setDescription(currentDescription);
  }

  async function handleSave(event: React.FormEvent) {
    event.preventDefault();
    if (!editingChannel) return;
    let config: Record<string, unknown>;
    try {
      config = JSON.parse(configText);
    } catch {
      toast.danger("Invalid configuration", "Configuration must be valid JSON.");
      return;
    }
    try {
      await setChannel.mutateAsync({ channel: editingChannel, input: { enabled, config, description: description || undefined } });
      toast.success("Channel configuration saved");
      setEditingChannel(null);
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not save channel", message);
    }
  }

  const configuredByChannel = new Map((channelsQuery.data ?? []).map((channel) => [channel.channel, channel]));

  return (
    <Card>
      <CardHeader>
        <CardTitle>Organization notification channels</CardTitle>
        <CardDescription>Where this organization&apos;s notifications actually get delivered.</CardDescription>
      </CardHeader>
      <CardContent>
        <SectionState isLoading={channelsQuery.isLoading} isError={channelsQuery.isError} error={channelsQuery.error} onRetry={() => channelsQuery.refetch()}>
          {!canEdit && (channelsQuery.data ?? []).length === 0 ? (
            <EmptyState title="No channels configured" description="Your role doesn't allow configuring these." />
          ) : (
            <ul className="flex flex-col gap-2">
              {NOTIFICATION_CHANNEL_KINDS.map((channel) => {
                const existing = configuredByChannel.get(channel);
                return (
                  <li key={channel} className="flex items-center justify-between gap-3 text-sm">
                    <div>
                      <p className="font-medium">{channel}</p>
                      <p className="text-muted-foreground text-xs">{existing ? (existing.enabled ? "Configured, enabled" : "Configured, disabled") : "Not configured"}</p>
                    </div>
                    {canEdit && (
                      <Button
                        variant="outline"
                        onClick={() => openEditor(channel, existing?.enabled ?? true, existing?.config ?? {}, existing?.description ?? "")}
                      >
                        {existing ? "Edit" : "Configure"}
                      </Button>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </SectionState>
      </CardContent>

      <Dialog open={editingChannel !== null} onClose={() => setEditingChannel(null)} title={`Configure ${editingChannel ?? ""}`}>
        <form onSubmit={handleSave} className="flex flex-col gap-4">
          <label className="flex items-center gap-2 text-sm">
            <Switch checked={enabled} onChange={(event) => setEnabled(event.target.checked)} aria-label="Channel enabled" />
            Enabled
          </label>
          <FormField label="Description">
            {(fieldProps) => <Input {...fieldProps} value={description} onChange={(event) => setDescription(event.target.value)} />}
          </FormField>
          <FormField label="Configuration (JSON)" description="Values here are echoed back unmasked by the backend — avoid pasting secrets you can't rotate easily.">
            {(fieldProps) => <Textarea {...fieldProps} value={configText} onChange={(event) => setConfigText(event.target.value)} className="min-h-32 font-mono text-xs" />}
          </FormField>
          <Button type="submit" loading={setChannel.isPending} className="w-fit">
            Save channel
          </Button>
        </form>
      </Dialog>
    </Card>
  );
}
