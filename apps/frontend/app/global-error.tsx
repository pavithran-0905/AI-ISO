"use client";

import { useEffect } from "react";

import { ErrorState } from "@/components/feedback/error-state";

/**
 * Next.js's own `global-error.tsx` convention — the boundary that
 * replaces the root layout entirely if `app/layout.tsx` itself throws.
 * Must render its own `<html>`/`<body>`, unlike `app/error.tsx`.
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <html lang="en">
      <body>
        <ErrorState
          title="An unexpected error occurred"
          description={error.message}
          onRetry={reset}
          className="min-h-screen"
        />
      </body>
    </html>
  );
}
