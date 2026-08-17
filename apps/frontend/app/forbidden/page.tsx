import Link from "next/link";

import { AccessDeniedState } from "@/components/feedback/access-denied-state";
import { buttonVariants } from "@/components/ui/button";

/** The 403 destination for a route-level `RequireRole` failure
 * (docs/frontend Prompt 001 §15). */
export default function ForbiddenPage() {
  return (
    <div className="bg-background text-foreground flex min-h-screen items-center justify-center">
      <AccessDeniedState
        variant="forbidden"
        action={
          <Link href="/" className={buttonVariants("primary")}>
            Back to dashboard
          </Link>
        }
      />
    </div>
  );
}
