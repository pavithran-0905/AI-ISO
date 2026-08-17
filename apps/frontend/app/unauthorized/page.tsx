import Link from "next/link";

import { AccessDeniedState } from "@/components/feedback/access-denied-state";
import { buttonVariants } from "@/components/ui/button";

/**
 * The 401 destination `AuthGuard` will redirect to once a login page
 * exists (docs/frontend Prompt 001 §15, completed by Prompt 003 §27).
 * `?from=` (set by `AuthGuard`) is the "return-to destination" — shown
 * here and preserved on the primary action so a future login page can
 * read it and send the user back to what they were trying to reach,
 * not always the dashboard. No "log in" action exists yet (no login
 * page — see `docs/frontend/architecture/authentication.md`); adding
 * one here would link to a route that 404s.
 */
export default async function UnauthorizedPage({
  searchParams,
}: {
  searchParams: Promise<{ from?: string }>;
}) {
  const { from } = await searchParams;

  return (
    <div className="bg-background text-foreground flex min-h-screen items-center justify-center">
      <AccessDeniedState
        variant="unauthorized"
        action={
          <div className="flex flex-col items-center gap-2">
            {from && (
              <p className="text-muted-foreground text-xs">
                You&apos;ll return to <span className="font-mono">{from}</span> once signed in.
              </p>
            )}
            <Link href="/" className={buttonVariants("primary")}>
              Back to dashboard
            </Link>
          </div>
        }
      />
    </div>
  );
}
