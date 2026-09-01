import Link from "next/link";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/data-display/card";
import { SectionState } from "@/features/dashboard/components/section-state";

/**
 * The reusable widget shell (§25): a `Card` + title/description/action
 * header + `SectionState`'s own loading/error/permission handling —
 * the same primitive `components/resource/resource-section.tsx`
 * already wraps for Resource Detail (Prompt 018), so there remains
 * exactly one loading/error implementation in the codebase (§25: "do
 * not duplicate loading/error patterns"), not two. A widget's *empty*
 * state stays each widget's own `children` concern, matching
 * `SectionState`'s own established precedent — "no alerts" and "no
 * reports" need different copy, so there's no generic `empty` prop to
 * get wrong.
 *
 * Every optional widget in `features/dashboard/lib/widget-registry.ts`
 * is built on this — one failing widget's `isError` never reaches its
 * siblings (§28), since each instance owns its own query and its own
 * `DashboardWidget`.
 */
export function DashboardWidget({
  title,
  description,
  action,
  isLoading,
  isError,
  error,
  onRetry,
  skeletonClassName,
  children,
}: {
  title: string;
  description?: string;
  /** A real, already-registered route only (§26/§47) — the caller is
   * responsible for that, matching `MetricCard`'s own `href` contract. */
  action?: { label: string; href: string };
  isLoading: boolean;
  isError: boolean;
  error?: unknown;
  onRetry?: () => void;
  skeletonClassName?: string;
  children: React.ReactNode;
}) {
  return (
    <Card className="flex h-full flex-col">
      <CardHeader className="flex flex-row items-start justify-between gap-2">
        <div className="flex flex-col gap-1">
          <CardTitle>{title}</CardTitle>
          {description && <CardDescription>{description}</CardDescription>}
        </div>
        {action && (
          <Link href={action.href} className="text-primary shrink-0 text-xs font-medium hover:underline">
            {action.label}
          </Link>
        )}
      </CardHeader>
      <CardContent className="flex-1">
        <SectionState
          isLoading={isLoading}
          isError={isError}
          error={error}
          onRetry={onRetry}
          skeletonClassName={skeletonClassName ?? "h-20 w-full"}
        >
          {children}
        </SectionState>
      </CardContent>
    </Card>
  );
}
