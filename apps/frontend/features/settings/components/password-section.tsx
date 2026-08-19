"use client";

import { ApiRequestError } from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/data-display/card";
import { Button } from "@/components/ui/button";
import { useRequestPasswordReset } from "@/features/settings/hooks/use-security";
import { toast } from "@/state/toast-store";

/**
 * No authenticated "change password with your current password" route
 * exists on this backend (confirmed absent from `authentication-service`
 * — only the anonymous, email-token-based forgot/reset-password flow).
 * This is the one real password-change mechanism available: send a
 * reset link to the caller's own already-verified email.
 */
export function PasswordSection({ email }: { email: string | null }) {
  const requestReset = useRequestPasswordReset();

  async function handleRequest() {
    if (!email) return;
    try {
      await requestReset.mutateAsync(email);
      toast.success("Reset link sent", `Check ${email} for instructions.`);
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not send reset link", message);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Password</CardTitle>
        <CardDescription>
          There&apos;s no in-app password change yet — we&apos;ll email you a reset link instead.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Button onClick={() => void handleRequest()} loading={requestReset.isPending} disabled={!email} variant="outline">
          Send password reset email
        </Button>
      </CardContent>
    </Card>
  );
}
