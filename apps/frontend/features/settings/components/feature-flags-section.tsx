"use client";

import { Plus } from "lucide-react";
import { useState } from "react";

import { ApiRequestError } from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/data-display/card";
import { EmptyState } from "@/components/feedback/empty-state";
import { StatusBadge } from "@/components/feedback/status-badge";
import { Button } from "@/components/ui/button";
import { IconButton } from "@/components/ui/icon-button";
import { Dialog } from "@/components/overlays/dialog";
import { FormField } from "@/components/forms/form-field";
import { Input } from "@/components/forms/input";
import { Switch } from "@/components/forms/switch";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useCreateFeatureFlag, useFeatureFlags, useUpdateFeatureFlag } from "@/features/settings/hooks/use-system-settings";
import { toast } from "@/state/toast-store";

/** `GET/POST /admin/feature-flags`, `PUT .../{id}` — richer than a
 * plain boolean: `isKilled` is a separate emergency kill-switch from
 * `isEnabled`, `rolloutPercentage` a real gradual-rollout float. Same
 * roles-claim permission gap as platform settings — see the developer
 * guide. */
export function FeatureFlagsSection() {
  const flagsQuery = useFeatureFlags();
  const createFlag = useCreateFeatureFlag();
  const updateFlag = useUpdateFeatureFlag();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [scope, setScope] = useState("global");

  async function handleCreate(event: React.FormEvent) {
    event.preventDefault();
    try {
      await createFlag.mutateAsync({ name, scope });
      toast.success("Feature flag created");
      setOpen(false);
      setName("");
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not create feature flag", message);
    }
  }

  async function handleToggle(flagId: string, isEnabled: boolean) {
    try {
      await updateFlag.mutateAsync({ flagId, input: { isEnabled } });
      toast.success(isEnabled ? "Flag enabled" : "Flag disabled");
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not update flag", message);
    }
  }

  async function handleKillSwitch(flagId: string, isKilled: boolean) {
    try {
      await updateFlag.mutateAsync({ flagId, input: { isKilled } });
      toast.success(isKilled ? "Flag killed" : "Kill switch cleared");
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not update flag", message);
    }
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <div>
          <CardTitle>Feature flags</CardTitle>
          <CardDescription>Gradual rollout, with a separate emergency kill switch.</CardDescription>
        </div>
        <IconButton icon={Plus} aria-label="Create feature flag" variant="outline" onClick={() => setOpen(true)} />
      </CardHeader>
      <CardContent>
        <SectionState isLoading={flagsQuery.isLoading} isError={flagsQuery.isError} error={flagsQuery.error} onRetry={() => flagsQuery.refetch()}>
          {flagsQuery.data &&
            (flagsQuery.data.length === 0 ? (
              <EmptyState title="No feature flags" description="Create one below." />
            ) : (
              <ul className="flex flex-col gap-2">
                {flagsQuery.data.map((flag) => (
                  <li key={flag.id} className="flex items-center justify-between gap-3 text-sm">
                    <div>
                      <p className="font-medium">
                        {flag.name} <span className="text-muted-foreground text-xs">({flag.scope})</span>
                      </p>
                      <p className="text-muted-foreground text-xs">{flag.rolloutPercentage}% rollout{flag.isKilled && " · killed"}</p>
                    </div>
                    <div className="flex items-center gap-3">
                      {flag.isKilled && <StatusBadge tone="danger" label="Killed" />}
                      <label className="flex items-center gap-1.5">
                        <Switch checked={flag.isEnabled} onChange={(event) => void handleToggle(flag.id, event.target.checked)} aria-label={`${flag.name} enabled`} />
                      </label>
                      <Button variant="outline" onClick={() => void handleKillSwitch(flag.id, !flag.isKilled)}>
                        {flag.isKilled ? "Clear kill switch" : "Kill"}
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            ))}
        </SectionState>
      </CardContent>

      <Dialog open={open} onClose={() => setOpen(false)} title="Create a feature flag">
        <form onSubmit={handleCreate} className="flex flex-col gap-4">
          <FormField label="Name" required>
            {(fieldProps) => <Input {...fieldProps} value={name} onChange={(event) => setName(event.target.value)} required />}
          </FormField>
          <FormField label="Scope" required description='e.g. "global", an organization id, or a feature area.'>
            {(fieldProps) => <Input {...fieldProps} value={scope} onChange={(event) => setScope(event.target.value)} required />}
          </FormField>
          <Button type="submit" loading={createFlag.isPending} disabled={!name} className="w-fit">
            Create flag
          </Button>
        </form>
      </Dialog>
    </Card>
  );
}
