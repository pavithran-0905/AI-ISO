"use client";

import { useRouter } from "next/navigation";

import { PageHeader } from "@/components/navigation/page-header";
import { Button } from "@/components/ui/button";
import { SectionState } from "@/features/dashboard/components/section-state";
import { ConnectorDetailView } from "@/features/settings/components/connector-detail-view";
import { useConnector } from "@/features/settings/hooks/use-integrations";

/** Connector detail — `/settings/integrations/[id]`. Not part of the
 * `SettingsLayout` sidebar (dynamic id, no static breadcrumb) — same
 * "Back to…" pattern as every other dynamic detail page in this app
 * (e.g. Infrastructure's asset detail, Prompt 011). */
export function ConnectorDetailPage({ connectorId }: { connectorId: string }) {
  const router = useRouter();
  const query = useConnector(connectorId);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={query.data?.name ?? "Connector"}
        secondaryActions={
          <Button variant="outline" onClick={() => router.push("/settings/integrations")}>
            Back to Integrations
          </Button>
        }
      />
      <SectionState isLoading={query.isLoading} isError={query.isError} error={query.error} onRetry={() => query.refetch()} skeletonClassName="h-96 w-full">
        {query.data && <ConnectorDetailView connector={query.data} />}
      </SectionState>
    </div>
  );
}
