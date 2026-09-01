"use client";

import { Sparkles } from "lucide-react";

import { AskAiButton } from "@/features/ai-assistant/components/ask-ai-button";
import { DashboardWidget } from "@/features/dashboard/components/dashboard-widget";
import { useRecommendations } from "@/features/ai-assistant/hooks/use-insights";

const DRAFT = "Summarize the current state of active alerts, automation activity, and asset health.";

/**
 * AI Insight (§21) — clearly labeled, and never itself a source of
 * AI-generated text: no dashboard-summarization endpoint exists on
 * this backend (confirmed absent), so this card never renders inline
 * AI output — it only shows a real, already-generated count
 * (`GET /ai/recommendations`, filtered to `status === "proposed"`,
 * i.e. genuinely awaiting a human decision — never recommendations
 * this card itself triggered) plus a button that opens a genuinely
 * separate Assistant conversation with a pre-filled, never-auto-sent
 * draft (`AskAiButton`, Prompt 010's own established pattern) —
 * mirroring Operations Workspace's own precedent (Prompt 019) of never
 * presenting AI-generated analysis as confirmed system state. No
 * automatic AI request is ever made by loading this card; the
 * recommendation count is a passive read of data generated elsewhere.
 * The count sub-fetch fails independently of the always-available
 * "Ask AI" action (§28: one part of a widget failing shouldn't hide
 * the rest of it), so this widget never gates its whole body behind
 * `DashboardWidget`'s own loading/error slot.
 */
export function AiInsightWidget({ organizationId }: { organizationId: string }) {
  const query = useRecommendations(organizationId);
  const pendingCount = query.data?.filter((recommendation) => recommendation.status === "proposed").length ?? null;

  return (
    <DashboardWidget title="AI Insight" description="AI Assistant, grounded in retrieved platform documentation." isLoading={false} isError={false}>
      <div className="flex flex-col gap-3">
        <p className="text-muted-foreground flex items-center gap-2 text-sm">
          <Sparkles className="size-4 shrink-0" aria-hidden="true" />
          {query.isLoading
            ? "Checking recommendations…"
            : query.isError || pendingCount === null
              ? "Ask AI Assistant about the current platform state."
              : pendingCount > 0
                ? `${pendingCount} recommendation${pendingCount === 1 ? "" : "s"} awaiting review.`
                : "No recommendations awaiting review."}
        </p>
        <AskAiButton draft={DRAFT} className="self-start" />
      </div>
    </DashboardWidget>
  );
}
