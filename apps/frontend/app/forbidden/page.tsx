"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { AccessDeniedState } from "@/components/feedback/access-denied-state";
import { Button, buttonVariants } from "@/components/ui/button";

/**
 * The 403 destination for a route-level `RequireRole` failure
 * (docs/frontend Prompt 001 §15, completed by Prompt 003 §28).
 * `AccessDeniedState`'s own "forbidden" copy already states what
 * happened (no permission) without exposing which specific
 * role/permission was required — deliberately, since that's the kind
 * of security-sensitive detail §28 says not to expose.
 */
export default function ForbiddenPage() {
  const router = useRouter();

  return (
    <div className="bg-background text-foreground flex min-h-screen items-center justify-center">
      <AccessDeniedState
        variant="forbidden"
        action={
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={() => router.back()}>
              Go back
            </Button>
            <Link href="/" className={buttonVariants("primary")}>
              Back to dashboard
            </Link>
          </div>
        }
      />
    </div>
  );
}
