"use client";

import { Lightbulb } from "lucide-react";
import Link from "next/link";
import { useMemo } from "react";

import { EmptyState } from "@/components/feedback/empty-state";
import { Skeleton } from "@/components/feedback/skeleton";
import { useRecommendations } from "@/features/ai-assistant/hooks/use-insights";

const PREVIEW_LIMIT = 5;

/** A compact preview of recommendations still awaiting a decision —
 * `status` has no server-side filter param (confirmed: `GET
 * /ai/recommendations` only accepts `organization_id`/`conversation_id`),
 * so `proposed` is filtered client-side over the full, unpaginated
 * result. Decide-or-not actions live on the full Recommendations page,
 * not duplicated here. */
export function PendingRecommendationsList({ organizationId }: { organizationId: string }) {
  const recommendationsQuery = useRecommendations(organizationId);

  const pending = useMemo(
    () => (recommendationsQuery.data ?? []).filter((r) => r.status === "proposed").slice(0, PREVIEW_LIMIT),
    [recommendationsQuery.data],
  );

  if (recommendationsQuery.isLoading) {
    return (
      <div className="flex flex-col gap-2" role="status" aria-label="Loading recommendations">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    );
  }

  if (pending.length === 0) {
    return <EmptyState icon={Lightbulb} title="Nothing awaiting a decision" />;
  }

  return (
    <ul className="flex flex-col gap-1">
      {pending.map((recommendation) => (
        <li key={recommendation.id}>
          <Link
            href="/intelligence/recommendations"
            className="hover:bg-muted focus-visible:ring-ring flex items-center justify-between gap-2 rounded-md p-2 text-sm focus-visible:ring-2 focus-visible:outline-none"
          >
            <span className="truncate">{recommendation.title}</span>
            <span className="text-muted-foreground shrink-0 text-xs">{recommendation.recommendationType}</span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
