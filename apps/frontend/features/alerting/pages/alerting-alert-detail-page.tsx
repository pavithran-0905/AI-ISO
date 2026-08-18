"use client";

import { useRouter } from "next/navigation";

import { PageHeader } from "@/components/navigation/page-header";
import { Button } from "@/components/ui/button";
import { SectionState } from "@/features/dashboard/components/section-state";
import { AlertDetailView } from "@/features/alerting/components/alert-detail-view";
import { useAlert } from "@/features/alerting/hooks/use-alert";

/**
 * Alert Detail (§9) — `/alerting/alerts/[id]`. Not registered in
 * `lib/route-registry.ts` (dynamic id, mirrors
 * `MonitoringAssetDetailPage`'s own reasoning) — renders its own "Back
 * to Alerts" action instead.
 */
export function AlertingAlertDetailPage({ alertId }: { alertId: string }) {
  const router = useRouter();
  const query = useAlert(alertId);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={query.data?.title ?? "Alert"}
        description={query.data ? `${query.data.source} · ${query.data.status}` : undefined}
        secondaryActions={
          <Button variant="outline" onClick={() => router.push("/alerting/alerts")}>
            Back to Alerts
          </Button>
        }
      />

      <SectionState
        isLoading={query.isLoading}
        isError={query.isError}
        error={query.error}
        onRetry={() => query.refetch()}
        skeletonClassName="h-96 w-full"
      >
        {query.data && <AlertDetailView alert={query.data} />}
      </SectionState>
    </div>
  );
}
