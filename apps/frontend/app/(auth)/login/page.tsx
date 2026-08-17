import type { Metadata } from "next";

import { GuestGuard } from "@/auth/guards";
import { isSafeReturnPath } from "@/auth/return-path";
import { Alert } from "@/components/feedback/alert";
import { LoginForm } from "@/app/(auth)/login/login-form";

export const metadata: Metadata = {
  title: "Sign in",
  robots: { index: false, follow: false },
};

/**
 * The production login page (docs/frontend Prompt 004 §3). A server
 * component so `?from=`/`?reason=` (set by `AuthGuard` on an
 * unauthenticated or expired-session redirect) can be read and
 * validated before anything renders, rather than flashing the form
 * first. `GuestGuard` handles session restoration (§21): an
 * already-authenticated visitor is redirected away instead of shown
 * the form again.
 */
export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ from?: string; reason?: string }>;
}) {
  const { from, reason } = await searchParams;
  const returnTo = isSafeReturnPath(from) ? from : "/";

  return (
    <GuestGuard redirectTo={returnTo}>
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-1 text-center">
          <h1 className="text-lg font-semibold tracking-tight">Sign in to AI-IOS</h1>
          <p className="text-muted-foreground text-sm">Enter your credentials to continue.</p>
        </div>
        {reason === "expired" && (
          <Alert tone="warning" title="Your session has expired">
            Please sign in again to continue.
          </Alert>
        )}
        <LoginForm returnTo={returnTo} />
      </div>
    </GuestGuard>
  );
}
