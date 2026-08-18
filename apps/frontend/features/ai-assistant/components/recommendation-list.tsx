"use client";

import { Lightbulb } from "lucide-react";

import { ApiRequestError } from "@/api/client";
import { EmptyState } from "@/components/feedback/empty-state";
import { Skeleton } from "@/components/feedback/skeleton";
import { StatusBadge } from "@/components/feedback/status-badge";
import { Button } from "@/components/ui/button";
import { CitationsList } from "@/features/ai-assistant/components/citations-list";
import { useDecideRecommendation, useRecommendations } from "@/features/ai-assistant/hooks/use-insights";
import { RECOMMENDATION_STATUS_TONE } from "@/features/ai-assistant/lib/status-maps";
import { usePermissions } from "@/permissions/hooks";
import { toast } from "@/state/toast-store";

/** No timestamp field exists on `Recommendation` (see its own
 * docstring) — shown in whatever order the backend returns, never
 * claimed to be sorted. */
export function RecommendationList({ organizationId }: { organizationId: string }) {
  const recommendationsQuery = useRecommendations(organizationId);
  const decideRecommendation = useDecideRecommendation();
  const { can } = usePermissions();

  async function handleDecide(recommendationId: string, accept: boolean) {
    try {
      await decideRecommendation.mutateAsync({ recommendationId, accept });
      toast.success(accept ? "Recommendation accepted" : "Recommendation rejected");
    } catch (error) {
      const description = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not record decision", description);
    }
  }

  if (recommendationsQuery.isLoading) {
    return (
      <div className="flex flex-col gap-2" role="status" aria-label="Loading recommendations">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }

  if (recommendationsQuery.isError) {
    return <p className="text-danger text-sm">Recommendations could not be loaded.</p>;
  }

  if (!recommendationsQuery.data || recommendationsQuery.data.length === 0) {
    return <EmptyState icon={Lightbulb} title="No recommendations yet" description="Generate one below." />;
  }

  return (
    <ul className="flex flex-col gap-3">
      {recommendationsQuery.data.map((recommendation) => (
        <li key={recommendation.id} className="border-border flex flex-col gap-2 rounded-md border p-3">
          <div className="flex items-start justify-between gap-2">
            <div className="flex flex-col gap-0.5">
              <span className="font-medium">{recommendation.title}</span>
              <span className="text-muted-foreground text-xs">{recommendation.recommendationType}</span>
            </div>
            <StatusBadge tone={RECOMMENDATION_STATUS_TONE[recommendation.status]} label={recommendation.status} />
          </div>

          <p className="text-sm">{recommendation.body}</p>
          {recommendation.rationale && <p className="text-muted-foreground text-xs">{recommendation.rationale}</p>}
          {recommendation.confidence !== null && (
            <p className="text-muted-foreground text-xs">Confidence: {Math.round(recommendation.confidence * 100)}%</p>
          )}
          <CitationsList citations={recommendation.citations} />

          {recommendation.status === "proposed" && can("approve") && (
            <div className="flex gap-2">
              <Button
                onClick={() => void handleDecide(recommendation.id, true)}
                loading={decideRecommendation.isPending}
                className="h-7 px-2 text-xs"
              >
                Accept
              </Button>
              <Button
                variant="outline"
                onClick={() => void handleDecide(recommendation.id, false)}
                loading={decideRecommendation.isPending}
                className="h-7 px-2 text-xs"
              >
                Reject
              </Button>
            </div>
          )}
        </li>
      ))}
    </ul>
  );
}
