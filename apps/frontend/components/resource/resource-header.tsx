import type { LucideIcon } from "lucide-react";

import { PageHeader } from "@/components/navigation/page-header";
import { formatRelativeTime } from "@/lib/relative-time";
import { typography } from "@/lib/typography";
import { cn } from "@/utils/cn";

/**
 * The reusable resource-detail header (Prompt 018 §5/§38) — built on
 * top of the existing `PageHeader` rather than a parallel
 * implementation, adding the one thing every resource investigation
 * page needs that a generic page header doesn't: an identity/meta row
 * (type, identifier, environment, last updated) beneath the title.
 * Every field is optional — a resource type with fewer real backend
 * fields (or a still-loading one) simply omits what it doesn't have,
 * never a placeholder dash for a field it never had (§5: "do not
 * overload the header").
 */
export function ResourceHeader({
  icon: Icon,
  title,
  resourceType,
  statusBadges,
  identifier,
  environment,
  lastUpdatedAt,
  primaryAction,
  secondaryActions,
}: {
  icon?: LucideIcon;
  title: string;
  resourceType?: string;
  /** Real status/health badges, rendered next to the title — the
   * caller decides which (a resource's own canonical status system,
   * never re-derived here). */
  statusBadges?: React.ReactNode;
  identifier?: string;
  environment?: string | null;
  lastUpdatedAt?: string | null;
  primaryAction?: React.ReactNode;
  secondaryActions?: React.ReactNode;
}) {
  const hasMetaRow = identifier || environment || lastUpdatedAt;

  return (
    <div className="flex flex-col gap-2">
      <PageHeader
        eyebrow={resourceType}
        title={title}
        status={
          (Icon || statusBadges) && (
            <span className="flex items-center gap-2">
              {Icon && <Icon className="text-muted-foreground size-5" aria-hidden="true" />}
              {statusBadges}
            </span>
          )
        }
        primaryAction={primaryAction}
        secondaryActions={secondaryActions}
      />
      {hasMetaRow && (
        <div className={cn(typography.caption, "text-muted-foreground flex flex-wrap items-center gap-x-4 gap-y-1")}>
          {identifier && <span className="font-mono">{identifier}</span>}
          {environment && <span>{environment}</span>}
          {lastUpdatedAt && (
            <span>
              Updated <time dateTime={lastUpdatedAt}>{formatRelativeTime(lastUpdatedAt)}</time>
            </span>
          )}
        </div>
      )}
    </div>
  );
}
