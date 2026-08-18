"use client";

import { RefreshCw } from "lucide-react";
import { useMemo } from "react";

import { Card, CardContent } from "@/components/data-display/card";
import { IconButton } from "@/components/ui/icon-button";
import { Skeleton } from "@/components/feedback/skeleton";
import { MetricCard } from "@/features/dashboard/components/metric-card";
import { useTools } from "@/features/ai-assistant/hooks/use-catalog";
import { useAiStatistics, useRecomputeAiStatistics } from "@/features/ai-assistant/hooks/use-insights";
import { formatPercent, formatUsd } from "@/features/ai-assistant/lib/format";
import { formatRelativeTime } from "@/lib/relative-time";
import { toast } from "@/state/toast-store";

function UsageBreakdown({ title, usage }: { title: string; usage: Record<string, number> }) {
  const entries = Object.entries(usage).sort(([, a], [, b]) => b - a);
  return (
    <Card>
      <CardContent className="flex flex-col gap-2 p-4">
        <p className="text-sm font-medium">{title}</p>
        {entries.length === 0 ? (
          <p className="text-muted-foreground text-xs">No activity recorded.</p>
        ) : (
          <ul className="flex flex-col gap-1">
            {entries.map(([key, count]) => (
              <li key={key} className="flex items-center justify-between gap-2 text-xs">
                <span className="text-muted-foreground truncate">{key}</span>
                <span className="tabular-nums">{count}</span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

/**
 * `AiStatistics` dashboard (§statistics). `agentUsage` is rendered here
 * as "Provider usage" — the backend's own field name is a misnomer
 * (see `AiStatistics`'s own docstring: it groups by `message.provider`,
 * there is no `agent_id` to group by). `toolUsage` keys are raw tool
 * UUIDs, resolved against `GET /ai/tools`. `estimatedCostUsd` carries a
 * visible caveat rather than being presented as authoritative, since
 * the backend's own per-token price table is hardcoded and incomplete
 * (see `docs/frontend/backend-v1-integration-limitations.md`).
 */
export function AiStatisticsSummary({ organizationId }: { organizationId: string }) {
  const statisticsQuery = useAiStatistics(organizationId);
  const toolsQuery = useTools(organizationId);
  const recompute = useRecomputeAiStatistics();

  const toolUsageByName = useMemo(() => {
    if (!statisticsQuery.data) return {};
    const nameById = new Map((toolsQuery.data ?? []).map((tool) => [tool.id, tool.name]));
    const resolved: Record<string, number> = {};
    for (const [toolId, count] of Object.entries(statisticsQuery.data.toolUsage)) {
      resolved[nameById.get(toolId) ?? toolId] = count;
    }
    return resolved;
  }, [statisticsQuery.data, toolsQuery.data]);

  async function handleRecompute() {
    try {
      await recompute.mutateAsync(organizationId);
      toast.success("Statistics recomputed");
    } catch {
      toast.danger("Could not recompute statistics", "Please try again.");
    }
  }

  if (statisticsQuery.isLoading) {
    return (
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4" role="status" aria-label="Loading statistics">
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-20 w-full" />
      </div>
    );
  }

  if (statisticsQuery.isError || !statisticsQuery.data) {
    return <p className="text-danger text-sm">Statistics could not be loaded.</p>;
  }

  const data = statisticsQuery.data;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-2">
        <p className="text-muted-foreground text-xs">
          Computed <time dateTime={data.computedAt}>{formatRelativeTime(data.computedAt)}</time>
        </p>
        <IconButton icon={RefreshCw} aria-label="Recompute statistics" variant="outline" loading={recompute.isPending} onClick={() => void handleRecompute()} />
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <MetricCard label="Conversations" value={data.totalConversations} />
        <MetricCard label="Messages" value={data.totalMessages} />
        <MetricCard label="Tool calls" value={data.totalToolCalls} />
        <MetricCard label="Avg. latency" value={`${Math.round(data.averageLatencyMs)}ms`} />
        <MetricCard label="Prompt tokens" value={data.totalPromptTokens.toLocaleString()} />
        <MetricCard label="Completion tokens" value={data.totalCompletionTokens.toLocaleString()} />
        <MetricCard label="Positive feedback" value={formatPercent(data.positiveFeedbackRate)} />
        <MetricCard label="Recommendation acceptance" value={formatPercent(data.recommendationAcceptanceRate)} />
      </div>

      <Card>
        <CardContent className="flex flex-col gap-1 p-4">
          <p className="text-muted-foreground text-xs">Estimated cost</p>
          <p className="text-2xl font-semibold tabular-nums">{formatUsd(data.estimatedCostUsd)}</p>
          <p className="text-muted-foreground text-xs">
            Based on a hardcoded, incomplete per-token price table — treat as directional, not a bill.
          </p>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <UsageBreakdown title="Tool usage" usage={toolUsageByName} />
        <UsageBreakdown title="Provider usage" usage={data.agentUsage} />
        <UsageBreakdown title="Model usage" usage={data.modelUsage} />
      </div>
    </div>
  );
}
