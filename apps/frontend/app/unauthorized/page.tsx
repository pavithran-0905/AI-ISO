import Link from "next/link";

import { AccessDeniedState } from "@/components/feedback/access-denied-state";
import { buttonVariants } from "@/components/ui/button";

/**
 * A generic 401 state (docs/frontend Prompt 001 §15). `AuthGuard`
 * (Prompt 004 §10) now redirects an unauthenticated visitor straight
 * to `/login?from=...&reason=...` rather than here, so nothing in the
 * app currently links to this page — it's kept as a standalone 401
 * destination for anything that isn't routed through `AuthGuard`
 * (e.g. a page that wants to show "unauthorized" without navigating
 * away first). `?from=` (the same "return-to destination" convention
 * `AuthGuard` uses) is forwarded onto the Sign In link so it isn't
 * lost if something does link here.
 */
export default async function UnauthorizedPage({
  searchParams,
}: {
  searchParams: Promise<{ from?: string }>;
}) {
  const { from } = await searchParams;
  const loginHref = from ? `/login?from=${encodeURIComponent(from)}` : "/login";

  return (
    <div className="bg-background text-foreground flex min-h-screen items-center justify-center">
      <AccessDeniedState
        variant="unauthorized"
        action={
          <div className="flex items-center gap-2">
            <Link href={loginHref} className={buttonVariants("primary")}>
              Sign in
            </Link>
            <Link href="/" className={buttonVariants("outline")}>
              Back to dashboard
            </Link>
          </div>
        }
      />
    </div>
  );
}
