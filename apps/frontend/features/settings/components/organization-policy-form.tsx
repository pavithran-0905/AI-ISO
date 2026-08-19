"use client";

import { useState } from "react";

import { ApiRequestError } from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/data-display/card";
import { Button } from "@/components/ui/button";
import { FormField } from "@/components/forms/form-field";
import { Input } from "@/components/forms/input";
import { Switch } from "@/components/forms/switch";
import { Textarea } from "@/components/forms/textarea";
import { useUpdateOrganizationSettings } from "@/features/settings/hooks/use-organization-settings";
import type { OrganizationSettings } from "@/features/settings/types";
import { toast } from "@/state/toast-store";

/**
 * `GET/PUT /organizations/{id}/settings` — full-replace `PUT`.
 * `passwordPolicy`/`storagePolicy`/`notificationPolicy` are opaque
 * JSON blobs with no defined sub-schema (confirmed: `dict[str, Any]`
 * on the backend) — round-tripped unchanged, not exposed as form
 * fields, same reasoning as `UserPreferences`'s own opaque fields.
 */
export function OrganizationPolicyForm({
  organizationId,
  settings,
  canEdit,
}: {
  organizationId: string;
  settings: OrganizationSettings;
  canEdit: boolean;
}) {
  const updateSettings = useUpdateOrganizationSettings(organizationId);
  const [mfaEnforced, setMfaEnforced] = useState(settings.mfaEnforced);
  const [allowedDomains, setAllowedDomains] = useState(settings.allowedDomains.join("\n"));
  const [defaultLanguage, setDefaultLanguage] = useState(settings.defaultLanguage);
  const [defaultTimezone, setDefaultTimezone] = useState(settings.defaultTimezone);
  const [sessionTimeoutMinutes, setSessionTimeoutMinutes] = useState(String(settings.sessionTimeoutMinutes));
  const [dataRetentionDays, setDataRetentionDays] = useState(String(settings.dataRetentionDays));

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    try {
      await updateSettings.mutateAsync({
        passwordPolicy: settings.passwordPolicy,
        mfaEnforced,
        allowedDomains: allowedDomains.split("\n").map((domain) => domain.trim()).filter(Boolean),
        defaultLanguage,
        defaultTimezone,
        sessionTimeoutMinutes: Number(sessionTimeoutMinutes) || settings.sessionTimeoutMinutes,
        dataRetentionDays: Number(dataRetentionDays) || settings.dataRetentionDays,
        storagePolicy: settings.storagePolicy,
        notificationPolicy: settings.notificationPolicy,
      });
      toast.success("Organization policy updated");
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not update policy", message);
    }
  }

  if (!canEdit) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Security & operational policy</CardTitle>
          <CardDescription>Your role doesn&apos;t allow editing this — showing current values.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-2 text-sm">
          <p>MFA enforced: {settings.mfaEnforced ? "Yes" : "No"}</p>
          <p>Allowed domains: {settings.allowedDomains.join(", ") || "None set"}</p>
          <p>Default language: {settings.defaultLanguage}</p>
          <p>Default timezone: {settings.defaultTimezone}</p>
          <p>Session timeout: {settings.sessionTimeoutMinutes} minutes</p>
          <p>Data retention: {settings.dataRetentionDays} days</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Security & operational policy</CardTitle>
        <CardDescription>Applies to every member of this organization.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex items-center gap-2">
            <Switch checked={mfaEnforced} onChange={(event) => setMfaEnforced(event.target.checked)} aria-label="Require MFA for all members" />
            <span className="text-sm">Require MFA for all members</span>
          </div>
          <FormField label="Allowed email domains" description="One per line. Empty means no restriction.">
            {(fieldProps) => <Textarea {...fieldProps} value={allowedDomains} onChange={(event) => setAllowedDomains(event.target.value)} />}
          </FormField>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <FormField label="Default language">
              {(fieldProps) => <Input {...fieldProps} value={defaultLanguage} onChange={(event) => setDefaultLanguage(event.target.value)} />}
            </FormField>
            <FormField label="Default timezone">
              {(fieldProps) => <Input {...fieldProps} value={defaultTimezone} onChange={(event) => setDefaultTimezone(event.target.value)} />}
            </FormField>
            <FormField label="Session timeout (minutes)">
              {(fieldProps) => <Input {...fieldProps} type="number" min={1} value={sessionTimeoutMinutes} onChange={(event) => setSessionTimeoutMinutes(event.target.value)} />}
            </FormField>
            <FormField label="Data retention (days)">
              {(fieldProps) => <Input {...fieldProps} type="number" min={1} value={dataRetentionDays} onChange={(event) => setDataRetentionDays(event.target.value)} />}
            </FormField>
          </div>
          <Button type="submit" loading={updateSettings.isPending} className="w-fit">
            Save policy
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
