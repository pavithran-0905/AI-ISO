"use client";

import Link from "next/link";

import { Card, CardContent } from "@/components/data-display/card";
import { StatusIndicator } from "@/components/data-display/status-indicator";
import { EmptyState } from "@/components/feedback/empty-state";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useAssetSearch } from "@/features/infrastructure/hooks/use-assets";
import { ASSET_HEALTH_TO_STATUS } from "@/features/infrastructure/lib/status-maps";

const CRITICAL_STATES = new Set(["critical", "unreachable"]);
/** A bounded page, client-filtered by `health` — `GET /inventory/search`
 * has no `health` query param (confirmed by source inspection: only
 * `asset_type`/`status`/`owner_id`/`project_id`/`q` are real filters),
 * so this can't be a server-side query. Scoped to one page (100 items,
 * newest-updated first) rather than the full dataset. */
const SCAN_PAGE_SIZE = 100;

/**
 * Critical Issues — assets whose `health` is `critical` or
 * `unreachable`, from the most recently updated page of results. Owned
 * by `features/infrastructure` (Prompt 011, which owns all
 * asset-fetching) and reused as-is by Monitoring's own Overview page —
 * the same "what requires attention" question either module would ask,
 * so it's shared rather than rebuilt twice.
 */
export function CriticalIssuesSection({ organizationId }: { organizationId: string }) {
  const query = useAssetSearch({
    organizationId,
    page: 1,
    pageSize: SCAN_PAGE_SIZE,
    sort: "updated_at:desc",
  });

  return (
    <SectionState
      isLoading={query.isLoading}
      isError={query.isError}
      error={query.error}
      onRetry={() => query.refetch()}
      skeletonClassName="h-40 w-full"
    >
      {query.data && (
        <CriticalList
          assets={query.data.items.filter((asset) => CRITICAL_STATES.has(asset.health))}
          truncated={query.data.pagination.total > SCAN_PAGE_SIZE}
        />
      )}
    </SectionState>
  );
}

function CriticalList({
  assets,
  truncated,
}: {
  assets: { id: string; name: string; displayName: string | null; health: "critical" | "unreachable" | string }[];
  truncated: boolean;
}) {
  if (assets.length === 0) {
    return <EmptyState title="No critical issues" description="Nothing is currently critical or unreachable." />;
  }

  return (
    <div className="flex flex-col gap-2">
      <ul className="flex flex-col gap-2">
        {assets.map((asset) => (
          <li key={asset.id}>
            <Link href={`/infrastructure/assets/${asset.id}`} className="block">
              <Card className="hover:border-muted-foreground/50 transition-colors">
                <CardContent className="flex items-center justify-between gap-3 p-3">
                  <p className="text-sm font-medium">{asset.displayName ?? asset.name}</p>
                  <StatusIndicator state={ASSET_HEALTH_TO_STATUS[asset.health as "critical" | "unreachable"]} />
                </CardContent>
              </Card>
            </Link>
          </li>
        ))}
      </ul>
      {truncated && (
        <p className="text-muted-foreground text-xs">
          Scanned the {SCAN_PAGE_SIZE} most recently updated assets — more may exist. See the full{" "}
          <Link href="/infrastructure/assets" className="underline">
            Assets
          </Link>{" "}
          list to search all of them.
        </p>
      )}
    </div>
  );
}
