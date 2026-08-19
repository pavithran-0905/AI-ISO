"use client";

import { useState } from "react";

import { ApiRequestError } from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/data-display/card";
import { StatusBadge } from "@/components/feedback/status-badge";
import { Button } from "@/components/ui/button";
import { FormField } from "@/components/forms/form-field";
import { Input } from "@/components/forms/input";
import { useDisableMfa, useEnableMfa, useVerifyMfa } from "@/features/settings/hooks/use-security";
import type { MfaEnableResult } from "@/features/settings/types";
import { toast } from "@/state/toast-store";

/**
 * `POST /auth/mfa/{enable,verify,disable}` — a real three-step TOTP
 * enrollment flow. The secret and recovery codes are shown exactly
 * once, from the `enable` response, and never persisted client-side
 * beyond this component's own transient state (cleared the moment
 * enrollment finishes or is abandoned) — §14's secret-handling rules
 * applied to the one genuinely secret value this feature ever
 * receives in full.
 */
export function MfaSection({ mfaEnabled }: { mfaEnabled: boolean }) {
  const enableMfa = useEnableMfa();
  const verifyMfa = useVerifyMfa();
  const disableMfa = useDisableMfa();
  const [enrollment, setEnrollment] = useState<MfaEnableResult | null>(null);
  const [verifyCode, setVerifyCode] = useState("");
  const [disableCode, setDisableCode] = useState("");
  const [showDisableForm, setShowDisableForm] = useState(false);

  async function handleStartEnrollment() {
    try {
      const result = await enableMfa.mutateAsync();
      setEnrollment(result);
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not start MFA enrollment", message);
    }
  }

  async function handleVerify(event: React.FormEvent) {
    event.preventDefault();
    try {
      await verifyMfa.mutateAsync(verifyCode);
      toast.success("MFA enabled");
      setEnrollment(null);
      setVerifyCode("");
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not verify code", message);
    }
  }

  async function handleDisable(event: React.FormEvent) {
    event.preventDefault();
    try {
      await disableMfa.mutateAsync(disableCode);
      toast.success("MFA disabled");
      setShowDisableForm(false);
      setDisableCode("");
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not disable MFA", message);
    }
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <div>
          <CardTitle>Multi-factor authentication</CardTitle>
          <CardDescription>A TOTP authenticator app, required at sign-in once enabled.</CardDescription>
        </div>
        <StatusBadge tone={mfaEnabled ? "success" : "neutral"} label={mfaEnabled ? "Enabled" : "Not enabled"} />
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {!mfaEnabled && !enrollment && (
          <Button onClick={handleStartEnrollment} loading={enableMfa.isPending} className="w-fit">
            Enable MFA
          </Button>
        )}

        {enrollment && (
          <div className="flex flex-col gap-4">
            <div>
              <p className="mb-1 text-sm font-medium">1. Scan or enter this into your authenticator app</p>
              <p className="text-muted-foreground font-mono text-xs break-all">{enrollment.otpauthUri}</p>
              <p className="text-muted-foreground mt-1 font-mono text-xs break-all">Secret: {enrollment.secret}</p>
            </div>
            <div>
              <p className="mb-1 text-sm font-medium">2. Save these recovery codes — shown only once</p>
              <ul className="grid grid-cols-2 gap-1 font-mono text-xs">
                {enrollment.recoveryCodes.map((code) => (
                  <li key={code}>{code}</li>
                ))}
              </ul>
            </div>
            <form onSubmit={handleVerify} className="flex flex-col gap-2">
              <p className="text-sm font-medium">3. Enter a code from your app to confirm</p>
              <FormField label="Verification code">
                {(fieldProps) => (
                  <Input {...fieldProps} value={verifyCode} onChange={(event) => setVerifyCode(event.target.value)} autoComplete="one-time-code" />
                )}
              </FormField>
              <div className="flex gap-2">
                <Button type="submit" loading={verifyMfa.isPending} disabled={!verifyCode}>
                  Confirm and enable
                </Button>
                <Button type="button" variant="outline" onClick={() => setEnrollment(null)}>
                  Cancel
                </Button>
              </div>
            </form>
          </div>
        )}

        {mfaEnabled && !showDisableForm && (
          <Button variant="outline" onClick={() => setShowDisableForm(true)} className="w-fit">
            Disable MFA
          </Button>
        )}

        {mfaEnabled && showDisableForm && (
          <form onSubmit={handleDisable} className="flex flex-col gap-2">
            <FormField label="Enter a current code to disable MFA">
              {(fieldProps) => (
                <Input {...fieldProps} value={disableCode} onChange={(event) => setDisableCode(event.target.value)} autoComplete="one-time-code" />
              )}
            </FormField>
            <div className="flex gap-2">
              <Button type="submit" variant="danger" loading={disableMfa.isPending} disabled={!disableCode}>
                Disable MFA
              </Button>
              <Button type="button" variant="outline" onClick={() => setShowDisableForm(false)}>
                Cancel
              </Button>
            </div>
          </form>
        )}
      </CardContent>
    </Card>
  );
}
