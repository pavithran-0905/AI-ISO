"use client";

import { useMemo, useState } from "react";

import { ApiRequestError } from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/data-display/card";
import { Button } from "@/components/ui/button";
import { FormField } from "@/components/forms/form-field";
import { Input } from "@/components/forms/input";
import { Select } from "@/components/forms/select";
import { useUpdateUserPreferences } from "@/features/settings/hooks/use-preferences";
import type { UserPreferences } from "@/features/settings/types";
import { useOrganizations } from "@/organization/use-organizations";
import { toast } from "@/state/toast-store";

/** A real browser API, not a fabricated list — `Intl.supportedValuesOf`
 * (available in every browser this app targets) enumerates the IANA
 * timezone database directly, so the picker never invents timezone
 * names. Falls back to a plain text input where unsupported. */
function useTimezoneOptions(): string[] | null {
  return useMemo(() => {
    const intlWithSupport = Intl as typeof Intl & { supportedValuesOf?: (key: string) => string[] };
    if (typeof intlWithSupport.supportedValuesOf !== "function") return null;
    try {
      return intlWithSupport.supportedValuesOf("timeZone");
    } catch {
      return null;
    }
  }, []);
}

/**
 * `GET/PUT /users/preferences` — a full-replace `PUT` (confirmed: no
 * `PATCH` exists), so every save resends the complete object. `theme`,
 * `dashboardPreferences`, `notificationPreferences`, and
 * `accessibility` are round-tripped unchanged — see the type's own
 * docstring for why they aren't editable here.
 */
export function PreferencesForm({ preferences }: { preferences: UserPreferences }) {
  const updatePreferences = useUpdateUserPreferences();
  const organizationsQuery = useOrganizations();
  const timezones = useTimezoneOptions();
  const [language, setLanguage] = useState(preferences.language);
  const [timezone, setTimezone] = useState(preferences.timezone);
  const [dateFormat, setDateFormat] = useState(preferences.dateFormat);
  const [timeFormat, setTimeFormat] = useState(preferences.timeFormat);
  const [defaultOrganizationId, setDefaultOrganizationId] = useState(preferences.defaultOrganizationId ?? "");

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    try {
      await updatePreferences.mutateAsync({
        language,
        theme: preferences.theme,
        timezone,
        dateFormat,
        timeFormat,
        dashboardPreferences: preferences.dashboardPreferences,
        notificationPreferences: preferences.notificationPreferences,
        accessibility: preferences.accessibility,
        defaultOrganizationId: defaultOrganizationId || null,
        defaultProjectId: preferences.defaultProjectId,
      });
      toast.success("Preferences updated");
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not update preferences", message);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Preferences</CardTitle>
        <CardDescription>Language, timezone, and formatting, synced across your devices.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <FormField label="Language" description="A BCP 47 language code, e.g. en or en-US.">
              {(fieldProps) => <Input {...fieldProps} value={language} onChange={(event) => setLanguage(event.target.value)} />}
            </FormField>
            <FormField label="Timezone">
              {(fieldProps) =>
                timezones ? (
                  <Select {...fieldProps} value={timezone} onChange={(event) => setTimezone(event.target.value)}>
                    {timezones.map((zone) => (
                      <option key={zone} value={zone}>
                        {zone}
                      </option>
                    ))}
                  </Select>
                ) : (
                  <Input {...fieldProps} value={timezone} onChange={(event) => setTimezone(event.target.value)} />
                )
              }
            </FormField>
            <FormField label="Date format" description={`Example: ${preferences.dateFormat}`}>
              {(fieldProps) => <Input {...fieldProps} value={dateFormat} onChange={(event) => setDateFormat(event.target.value)} />}
            </FormField>
            <FormField label="Time format" description='"24h" or "12h"'>
              {(fieldProps) => <Input {...fieldProps} value={timeFormat} onChange={(event) => setTimeFormat(event.target.value)} />}
            </FormField>
          </div>
          <FormField label="Default organization" description="Which organization to show first when you sign in.">
            {(fieldProps) => (
              <Select {...fieldProps} value={defaultOrganizationId} onChange={(event) => setDefaultOrganizationId(event.target.value)}>
                <option value="">No default</option>
                {(organizationsQuery.data ?? []).map((organization) => (
                  <option key={organization.id} value={organization.id}>
                    {organization.displayName}
                  </option>
                ))}
              </Select>
            )}
          </FormField>
          <Button type="submit" loading={updatePreferences.isPending} className="w-fit">
            Save preferences
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
