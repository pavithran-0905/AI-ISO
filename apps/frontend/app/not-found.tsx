"use client";

import { FileQuestion } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { Button, buttonVariants } from "@/components/ui/button";

/**
 * Next.js's own `not-found.tsx` convention — the reusable 404 primitive
 * (docs/frontend Prompt 001 §15/§19, completed by Prompt 003 §26).
 * Shows the attempted path ("current context where possible") and
 * offers two distinct recovery actions: a generic return (browser
 * back) and a specific one (the dashboard) — not just one, since
 * "back" isn't always "home" for a deep link a user followed.
 */
export default function NotFound() {
  const pathname = usePathname();
  const router = useRouter();

  return (
    <div className="bg-background text-foreground flex min-h-screen flex-col items-center justify-center gap-3 p-8 text-center">
      <FileQuestion className="text-muted-foreground size-8" aria-hidden="true" />
      <div className="flex flex-col gap-1">
        <p className="text-sm font-medium">Page not found</p>
        <p className="text-muted-foreground text-sm">
          The page you&apos;re looking for doesn&apos;t exist.
        </p>
        {pathname && (
          <p className="text-muted-foreground font-mono text-xs">
            {pathname}
          </p>
        )}
      </div>
      <div className="flex items-center gap-2">
        <Button variant="outline" onClick={() => router.back()}>
          Go back
        </Button>
        <Link href="/" className={buttonVariants("primary")}>
          Back to dashboard
        </Link>
      </div>
    </div>
  );
}
