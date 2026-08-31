import { Card, CardContent, CardHeader, CardTitle } from "@/components/data-display/card";
import { SectionState } from "@/features/dashboard/components/section-state";

/**
 * The reusable resource-detail section shell (§28: "each resource
 * section should be independently resilient" — one section's own
 * `isError` never blanks the others, since each `ResourceSection`
 * instance owns its own `SectionState`, not a page-wide one). Every
 * real section this session's resource pages render (Overview, State,
 * Relationships, Topology, Configuration, ...) is `Card` +
 * `CardHeader`/`CardTitle` + loading/error/content — this only
 * extracts that repeated shape, never invents new section semantics.
 */
export function ResourceSection({
  title,
  action,
  isLoading,
  isError,
  error,
  onRetry,
  children,
}: {
  title: string;
  action?: React.ReactNode;
  isLoading?: boolean;
  isError?: boolean;
  error?: unknown;
  onRetry?: () => void;
  children: React.ReactNode;
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <CardTitle>{title}</CardTitle>
        {action}
      </CardHeader>
      <CardContent>
        {isLoading !== undefined || isError !== undefined ? (
          <SectionState isLoading={Boolean(isLoading)} isError={Boolean(isError)} error={error} onRetry={onRetry} skeletonClassName="h-24 w-full">
            {children}
          </SectionState>
        ) : (
          children
        )}
      </CardContent>
    </Card>
  );
}
