"use client";

import { PageHeader } from "@/components/navigation/page-header";
import { MonitoringSubNav } from "@/features/monitoring/components/monitoring-sub-nav";
import { ServiceHealthList } from "@/features/monitoring/components/service-health-list";

export function MonitoringServicesPage() {
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Service Health"
        description="Per-service health derived from the platform's dependency topology."
      />
      <MonitoringSubNav />
      <ServiceHealthList />
    </div>
  );
}
