import Link from "next/link";
import { FileQuestion } from "lucide-react";

import { buttonVariants } from "@/components/ui/button";

/** Next.js's own `not-found.tsx` convention — the reusable 404 primitive
 * (docs/frontend Prompt 001 §15/§19). */
export default function NotFound() {
  return (
    <div className="bg-background text-foreground flex min-h-screen flex-col items-center justify-center gap-3 p-8 text-center">
      <FileQuestion className="text-muted-foreground size-8" aria-hidden="true" />
      <div className="flex flex-col gap-1">
        <p className="text-sm font-medium">Page not found</p>
        <p className="text-muted-foreground text-sm">The page you&apos;re looking for doesn&apos;t exist.</p>
      </div>
      <Link href="/" className={buttonVariants("outline")}>
        Back to dashboard
      </Link>
    </div>
  );
}
