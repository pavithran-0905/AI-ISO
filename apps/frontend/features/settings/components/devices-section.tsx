"use client";

import { ShieldOff } from "lucide-react";

import { ApiRequestError } from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/data-display/card";
import { EmptyState } from "@/components/feedback/empty-state";
import { IconButton } from "@/components/ui/icon-button";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useDevices, useRevokeDevice } from "@/features/settings/hooks/use-security";
import { toast } from "@/state/toast-store";

/** `GET/DELETE /auth/devices` — every device on record for the
 * caller, self-scoped by the backend. */
export function DevicesSection() {
  const devicesQuery = useDevices();
  const revokeDevice = useRevokeDevice();

  async function handleRevoke(deviceId: string) {
    try {
      await revokeDevice.mutateAsync(deviceId);
      toast.success("Device revoked");
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not revoke device", message);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Trusted devices</CardTitle>
        <CardDescription>Devices that have signed in as you.</CardDescription>
      </CardHeader>
      <CardContent>
        <SectionState isLoading={devicesQuery.isLoading} isError={devicesQuery.isError} error={devicesQuery.error} onRetry={() => devicesQuery.refetch()}>
          {devicesQuery.data &&
            (devicesQuery.data.length === 0 ? (
              <EmptyState title="No devices on record" description="Devices appear here after you sign in." />
            ) : (
              <ul className="flex flex-col gap-2">
                {devicesQuery.data.map((device) => (
                  <li key={device.id} className="flex items-center justify-between gap-3 text-sm">
                    <div>
                      <p className="font-medium">
                        {device.deviceName ?? "Unknown device"}
                        {device.isTrusted && <span className="text-success ml-2 text-xs">Trusted</span>}
                      </p>
                      <p className="text-muted-foreground text-xs">
                        {[device.browser, device.operatingSystem, device.location].filter(Boolean).join(" · ") || "No details recorded"}
                        {device.lastLoginAt ? ` · Last used ${new Date(device.lastLoginAt).toLocaleDateString()}` : ""}
                      </p>
                    </div>
                    <IconButton
                      icon={ShieldOff}
                      aria-label={`Revoke ${device.deviceName ?? "device"}`}
                      variant="ghost"
                      onClick={() => void handleRevoke(device.id)}
                      loading={revokeDevice.isPending}
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
