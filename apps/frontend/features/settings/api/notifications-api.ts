/**
 * `services/notification-center-service` — per-user notification
 * preferences (`/notifications/preferences`) and organization-level
 * channel configuration (`/notifications/channels`, e.g. a Slack
 * webhook URL) — two distinct concepts, never conflated. See
 * `NotificationChannelConfig`'s own docstring for the real backend
 * secret-masking gap this frontend defends against.
 */

import { apiClient } from "@/api/client";
import type {
  NotificationChannelConfig,
  NotificationPreferences,
  UpdateNotificationChannelInput,
  UpdateNotificationPreferencesInput,
} from "@/features/settings/types";

interface PreferenceResponseBody {
  id: string;
  organization_id: string;
  user_id: string;
  preferred_channels: string[];
  muted_categories: string[];
  unsubscribed_channels: string[];
  channel_priority: string[];
  device_tokens: string[];
  quiet_hours_start: string | null;
  quiet_hours_end: string | null;
  language: string | null;
  timezone: string | null;
  digest_frequency: string;
  muted: boolean;
  priority_overrides: Record<string, unknown>;
}

function toPreferences(body: PreferenceResponseBody): NotificationPreferences {
  return {
    id: body.id,
    organizationId: body.organization_id,
    userId: body.user_id,
    preferredChannels: body.preferred_channels as NotificationPreferences["preferredChannels"],
    mutedCategories: body.muted_categories as NotificationPreferences["mutedCategories"],
    unsubscribedChannels: body.unsubscribed_channels as NotificationPreferences["unsubscribedChannels"],
    channelPriority: body.channel_priority as NotificationPreferences["channelPriority"],
    deviceTokens: body.device_tokens,
    quietHoursStart: body.quiet_hours_start,
    quietHoursEnd: body.quiet_hours_end,
    language: body.language,
    timezone: body.timezone,
    digestFrequency: body.digest_frequency as NotificationPreferences["digestFrequency"],
    muted: body.muted,
    priorityOverrides: body.priority_overrides,
  };
}

interface ChannelConfigResponseBody {
  id: string;
  organization_id: string;
  channel: string;
  enabled: boolean;
  config: Record<string, unknown>;
  description: string | null;
}

function toChannelConfig(body: ChannelConfigResponseBody): NotificationChannelConfig {
  return {
    id: body.id,
    organizationId: body.organization_id,
    channel: body.channel as NotificationChannelConfig["channel"],
    enabled: body.enabled,
    config: body.config,
    description: body.description,
  };
}

export const notificationsApi = {
  async getPreferences(organizationId: string): Promise<NotificationPreferences> {
    const query = new URLSearchParams({ organization_id: organizationId });
    const body = await apiClient.get<PreferenceResponseBody>(`/notifications/preferences?${query.toString()}`);
    return toPreferences(body);
  },

  /** Genuinely partial-safe — confirmed: `PreferenceService.update`
   * only applies a field when the caller actually sent a non-null
   * value, unlike every user-management-service PUT. Still sends every
   * field this feature knows about, since `undefined` keys are simply
   * omitted from the JSON body by `JSON.stringify`, which the backend
   * correctly treats as "leave unchanged." */
  async updatePreferences(organizationId: string, input: UpdateNotificationPreferencesInput): Promise<NotificationPreferences> {
    const query = new URLSearchParams({ organization_id: organizationId });
    const body = await apiClient.put<PreferenceResponseBody>(`/notifications/preferences?${query.toString()}`, {
      preferred_channels: input.preferredChannels,
      muted_categories: input.mutedCategories,
      unsubscribed_channels: input.unsubscribedChannels,
      channel_priority: input.channelPriority,
      quiet_hours_start: input.quietHoursStart,
      quiet_hours_end: input.quietHoursEnd,
      language: input.language,
      timezone: input.timezone,
      digest_frequency: input.digestFrequency,
      muted: input.muted,
    });
    return toPreferences(body);
  },

  async listChannels(organizationId: string): Promise<NotificationChannelConfig[]> {
    const query = new URLSearchParams({ organization_id: organizationId });
    const body = await apiClient.get<ChannelConfigResponseBody[]>(`/notifications/channels?${query.toString()}`);
    return body.map(toChannelConfig);
  },

  /** Create-or-replace this organization's config for one channel
   * kind. **Security note**: the backend echoes `config` back
   * completely unmasked (confirmed absent of any redaction) — never
   * log or display a `config` value from this route without masking
   * credential-shaped keys first. */
  async setChannel(
    organizationId: string,
    channel: string,
    input: UpdateNotificationChannelInput,
  ): Promise<NotificationChannelConfig> {
    const query = new URLSearchParams({ organization_id: organizationId });
    const body = await apiClient.put<ChannelConfigResponseBody>(
      `/notifications/channels/${channel}?${query.toString()}`,
      { enabled: input.enabled, config: input.config, description: input.description },
    );
    return toChannelConfig(body);
  },
};
