import { ApiRequestError } from "@/api/client";
import { AccessDeniedState } from "@/components/feedback/access-denied-state";
import { ErrorState } from "@/components/feedback/error-state";
import { Skeleton } from "@/components/feedback/skeleton";

/**
 * Shared loading/error/permission handling for a single dashboard
 * section's query (§16/§19/§20: a failure in one section must never
 * blank the rest of the dashboard, and a 403 needs a distinct,
 * permission-safe message rather than a generic "retry" prompt).
 * Empty-vs-populated is left to each section's own `children` render
 * prop, since "no alerts" and "no assets" need different copy (§18).
 */
export function SectionState({
  isLoading,
  isError,
  error,
  onRetry,
  skeletonClassName,
  children,
}: {
  isLoading: boolean;
  isError: boolean;
  error?: unknown;
  onRetry?: () => void;
  skeletonClassName?: string;
  children: React.ReactNode;
}) {
  if (isLoading) {
    return (
      <div role="status" aria-label="Loading">
        <Skeleton className={skeletonClassName ?? "h-24 w-full"} />
      </div>
    );
  }

  if (isError) {
    if (error instanceof ApiRequestError && error.status === 403) {
      return <AccessDeniedState variant="forbidden" />;
    }
    return <ErrorState description={describeError(error)} onRetry={onRetry} />;
  }

  return children;
}

function describeError(error: unknown): string {
  if (error instanceof ApiRequestError) {
    if (error.status >= 500) return "This data is temporarily unavailable. Please try again.";
    return error.message;
  }
  return "Unable to load this data right now.";
}
