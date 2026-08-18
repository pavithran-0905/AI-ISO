"use client";

import { PageHeader } from "@/components/navigation/page-header";
import { EventTimeline } from "@/features/monitoring/components/event-timeline";
import { MonitoringSubNav } from "@/features/monitoring/components/monitoring-sub-nav";

export function MonitoringEventsPage() {
  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Events" description="Platform, infrastructure, deployment, and configuration events." />
      <MonitoringSubNav />
      <EventTimeline />
    </div>
  );
}
