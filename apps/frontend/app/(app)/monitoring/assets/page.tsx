import { Suspense } from "react";

import { LoadingState } from "@/components/feedback/loading-state";
import { MonitoringAssetsPage } from "@/features/monitoring/pages/monitoring-assets-page";

export default function Page() {
  return (
    <Suspense fallback={<LoadingState label="Loading assets…" />}>
      <MonitoringAssetsPage />
    </Suspense>
  );
}
