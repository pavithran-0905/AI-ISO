"use client";

import { useEffect } from "react";

import { ErrorState } from "@/components/feedback/error-state";

/**
 * Next.js's own `error.tsx` convention — a client-side error boundary
 * nested inside the existing root layout (so it must NOT render its own
 * `<html>`/`<body>` — see `app/global-error.tsx` for the boundary that
 * replaces the root layout itself). Deliberately minimal: reports to the
 * console for now; a later prompt wires this to a real error-reporting
 * service.
 */
export default function SegmentError({
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
    <ErrorState
      title="An unexpected error occurred"
      description={error.message}
      onRetry={reset}
      className="min-h-screen"
    />
  );
}
