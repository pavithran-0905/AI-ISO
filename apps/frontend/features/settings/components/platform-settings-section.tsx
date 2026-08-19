"use client";

import { Plus } from "lucide-react";
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
import { usePlatformSettings, useUpsertPlatformSetting } from "@/features/settings/hooks/use-system-settings";
import { toast } from "@/state/toast-store";

/**
 * `GET/PUT /admin/settings` — a flat key/value store, `value` is
 * arbitrary JSON, not a typed schema (confirmed: no boolean-toggle
 * shape like feature flags have). No `version` field exists.
 * **Permission note**: `PUT` requires an `admin`/`administrator`/
 * `platform_admin`/`super_admin` role in the JWT's `roles` array
 * claim — a claim current tokens never populate (see the developer
 * guide) — so this save will genuinely 403 today for every session;
 * that's shown as a real error, never papered over.
 */
export function PlatformSettingsSection() {
  const settingsQuery = usePlatformSettings();
  const upsertSetting = useUpsertPlatformSetting();
  const [open, setOpen] = useState(false);
  const [key, setKey] = useState("");
  const [value, setValue] = useState("");
  const [description, setDescription] = useState("");

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    try {
      await upsertSetting.mutateAsync({ key, value, description: description || undefined });
      toast.success("Setting saved");
      setOpen(false);
      setKey("");
      setValue("");
      setDescription("");
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not save setting", message);
    }
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <div>
          <CardTitle>Platform settings</CardTitle>
          <CardDescription>A flat key/value store, shared across every organization.</CardDescription>
        </div>
        <IconButton icon={Plus} aria-label="Add setting" variant="outline" onClick={() => setOpen(true)} />
      </CardHeader>
      <CardContent>
        <SectionState isLoading={settingsQuery.isLoading} isError={settingsQuery.isError} error={settingsQuery.error} onRetry={() => settingsQuery.refetch()}>
          {settingsQuery.data &&
            (settingsQuery.data.length === 0 ? (
              <EmptyState title="No platform settings recorded" description="Add one below." />
            ) : (
              <ul className="flex flex-col gap-2">
                {settingsQuery.data.map((setting) => (
                  <li key={setting.id} className="text-sm">
                    <p className="font-mono font-medium">{setting.key}</p>
                    <p className="text-muted-foreground text-xs break-all">{JSON.stringify(setting.value)}</p>
                    {setting.description && <p className="text-muted-foreground text-xs">{setting.description}</p>}
                  </li>
                ))}
              </ul>
            ))}
        </SectionState>
      </CardContent>

      <Dialog open={open} onClose={() => setOpen(false)} title="Set a platform setting">
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <FormField label="Key" required>
            {(fieldProps) => <Input {...fieldProps} value={key} onChange={(event) => setKey(event.target.value)} required />}
          </FormField>
          <FormField label="Value" required description="Sent as a plain string.">
            {(fieldProps) => <Input {...fieldProps} value={value} onChange={(event) => setValue(event.target.value)} required />}
          </FormField>
          <FormField label="Description">
            {(fieldProps) => <Input {...fieldProps} value={description} onChange={(event) => setDescription(event.target.value)} />}
          </FormField>
          <Button type="submit" loading={upsertSetting.isPending} disabled={!key || !value} className="w-fit">
            Save setting
          </Button>
        </form>
      </Dialog>
    </Card>
  );
}
