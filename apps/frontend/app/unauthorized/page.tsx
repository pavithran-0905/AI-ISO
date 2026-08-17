import Link from "next/link";

import { AccessDeniedState } from "@/components/feedback/access-denied-state";
import { buttonVariants } from "@/components/ui/button";

/** The 401 destination `AuthGuard` will redirect to once a login page
 * exists (docs/frontend Prompt 001 §15). */
export default function UnauthorizedPage() {
  return (
    <div className="bg-background text-foreground flex min-h-screen items-center justify-center">
      <AccessDeniedState
        variant="unauthorized"
        action={
          <Link href="/" className={buttonVariants("primary")}>
            Back to dashboard
          </Link>
        }
      />
    </div>
  );
}
