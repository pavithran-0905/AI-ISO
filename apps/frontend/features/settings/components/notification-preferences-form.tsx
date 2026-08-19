"use client";

import { useState } from "react";

import { ApiRequestError } from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/data-display/card";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/forms/checkbox";
import { FormField } from "@/components/forms/form-field";
import { Input } from "@/components/forms/input";
import { Label } from "@/components/forms/label";
import { Select } from "@/components/forms/select";
import { Switch } from "@/components/forms/switch";
import { useUpdateNotificationPreferences } from "@/features/settings/hooks/use-notification-settings";
import {
  DIGEST_FREQUENCIES,
  NOTIFICATION_CATEGORIES,
  NOTIFICATION_CHANNEL_KINDS,
  type NotificationCategoryValue,
  type NotificationChannelKindValue,
  type NotificationPreferences,
} from "@/features/settings/types";
import { toast } from "@/state/toast-store";

function toggleInList<T>(list: T[], value: T): T[] {
  return list.includes(value) ? list.filter((item) => item !== value) : [...list, value];
}

/**
 * `GET/PUT /notifications/preferences?organization_id=` — genuinely
 * partial-safe on the backend, but this form still submits every
 * field it knows about (see the api module's own docstring).
 * `deviceTokens`/`priorityOverrides` are round-tripped unchanged, no
 * form control built for either (opaque/advanced).
 */
export function NotificationPreferencesForm({ organizationId, preferences }: { organizationId: string; preferences: NotificationPreferences }) {
  const updatePreferences = useUpdateNotificationPreferences(organizationId);
  const [preferredChannels, setPreferredChannels] = useState<NotificationChannelKindValue[]>(preferences.preferredChannels);
  const [mutedCategories, setMutedCategories] = useState<NotificationCategoryValue[]>(preferences.mutedCategories);
  const [quietHoursStart, setQuietHoursStart] = useState(preferences.quietHoursStart ?? "");
  const [quietHoursEnd, setQuietHoursEnd] = useState(preferences.quietHoursEnd ?? "");
  const [digestFrequency, setDigestFrequency] = useState(preferences.digestFrequency);
  const [muted, setMuted] = useState(preferences.muted);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    try {
      await updatePreferences.mutateAsync({
        preferredChannels,
        mutedCategories,
        unsubscribedChannels: preferences.unsubscribedChannels,
        channelPriority: preferences.channelPriority,
        deviceTokens: preferences.deviceTokens,
        quietHoursStart: quietHoursStart || null,
        quietHoursEnd: quietHoursEnd || null,
        language: preferences.language,
        timezone: preferences.timezone,
        digestFrequency,
        muted,
        priorityOverrides: preferences.priorityOverrides,
      });
      toast.success("Notification preferences updated");
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not update preferences", message);
    }
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <div>
          <CardTitle>My notification preferences</CardTitle>
          <CardDescription>How and when AI-IOS reaches you.</CardDescription>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <Switch checked={muted} onChange={(event) => setMuted(event.target.checked)} aria-label="Mute all notifications" />
          Mute all
        </label>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="flex flex-col gap-5">
          <fieldset className="flex flex-col gap-1.5">
            <legend className="text-sm font-medium">Preferred channels</legend>
            <div className="flex flex-wrap gap-3">
              {NOTIFICATION_CHANNEL_KINDS.map((channel) => (
                <label key={channel} className="flex items-center gap-1.5 text-sm">
                  <Checkbox
                    checked={preferredChannels.includes(channel)}
                    onChange={() => setPreferredChannels((current) => toggleInList(current, channel))}
                  />
                  {channel}
                </label>
              ))}
            </div>
          </fieldset>

          <fieldset className="flex flex-col gap-1.5">
            <legend className="text-sm font-medium">Muted categories</legend>
            <div className="flex flex-wrap gap-3">
              {NOTIFICATION_CATEGORIES.map((category) => (
                <label key={category} className="flex items-center gap-1.5 text-sm">
                  <Checkbox
                    checked={mutedCategories.includes(category)}
                    onChange={() => setMutedCategories((current) => toggleInList(current, category))}
                  />
                  {category}
                </label>
              ))}
            </div>
          </fieldset>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="quiet-start">Quiet hours start</Label>
              <Input id="quiet-start" type="time" value={quietHoursStart} onChange={(event) => setQuietHoursStart(event.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="quiet-end">Quiet hours end</Label>
              <Input id="quiet-end" type="time" value={quietHoursEnd} onChange={(event) => setQuietHoursEnd(event.target.value)} />
            </div>
            <FormField label="Digest frequency">
              {(fieldProps) => (
                <Select {...fieldProps} value={digestFrequency} onChange={(event) => setDigestFrequency(event.target.value as typeof digestFrequency)}>
                  {DIGEST_FREQUENCIES.map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </Select>
              )}
            </FormField>
          </div>

          <Button type="submit" loading={updatePreferences.isPending} className="w-fit">
            Save preferences
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
