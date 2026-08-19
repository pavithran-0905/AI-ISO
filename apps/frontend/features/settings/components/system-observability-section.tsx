"use client";

import { useState } from "react";

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/data-display/card";
import { EmptyState } from "@/components/feedback/empty-state";
import { Tabs } from "@/components/navigation/tabs";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useSystemDiagnostics, useSystemReports, useSystemStatistics } from "@/features/settings/hooks/use-system-settings";

const TABS = [
  { id: "diagnostics", label: "Diagnostics" },
  { id: "statistics", label: "Statistics" },
  { id: "reports", label: "Reports" },
];

/** `GET /admin/diagnostics`, `/admin/statistics`, `/admin/reports` —
 * all read-only. Reports expose metadata only — no content/download
 * field exists on that response (confirmed absent). */
export function SystemObservabilitySection() {
  const [activeTab, setActiveTab] = useState("diagnostics");
  const diagnosticsQuery = useSystemDiagnostics();
  const statisticsQuery = useSystemStatistics();
  const reportsQuery = useSystemReports();

  return (
    <Card>
      <CardHeader>
        <CardTitle>Observability</CardTitle>
        <CardDescription>Read-only.</CardDescription>
      </CardHeader>
      <CardContent>
        <Tabs items={TABS} activeId={activeTab} onChange={setActiveTab}>
          {activeTab === "diagnostics" && (
            <SectionState isLoading={diagnosticsQuery.isLoading} isError={diagnosticsQuery.isError} error={diagnosticsQuery.error} onRetry={() => diagnosticsQuery.refetch()}>
              {diagnosticsQuery.data &&
                (diagnosticsQuery.data.length === 0 ? (
                  <EmptyState title="No diagnostics recorded" description="Nothing has run yet." />
                ) : (
                  <ul className="flex flex-col gap-1.5 text-sm">
                    {diagnosticsQuery.data.map((entry) => (
                      <li key={entry.id} className="flex justify-between">
                        <span>{entry.category}</span>
                        <span className="text-muted-foreground text-xs">
                          {entry.status}
                          {entry.latencyMs !== null ? ` · ${entry.latencyMs}ms` : ""} · {new Date(entry.ranAt).toLocaleString()}
                        </span>
                      </li>
                    ))}
                  </ul>
                ))}
            </SectionState>
          )}

          {activeTab === "statistics" && (
            <SectionState isLoading={statisticsQuery.isLoading} isError={statisticsQuery.isError} error={statisticsQuery.error} onRetry={() => statisticsQuery.refetch()}>
              {statisticsQuery.data &&
                (statisticsQuery.data.length === 0 ? (
                  <EmptyState title="No statistics recorded yet" description="Rollups populate over time." />
                ) : (
                  <ul className="flex flex-col gap-1.5 text-sm">
                    {statisticsQuery.data.map((window) => (
                      <li key={window.windowStart} className="flex justify-between">
                        <span>
                          {new Date(window.windowStart).toLocaleDateString()} – {new Date(window.windowEnd).toLocaleDateString()}
                        </span>
                        <span className="text-muted-foreground text-xs">
                          {window.tenantCount} tenants · {window.userCount} users · {(window.platformAvailabilityFraction * 100).toFixed(2)}% availability
                        </span>
                      </li>
                    ))}
                  </ul>
                ))}
            </SectionState>
          )}

          {activeTab === "reports" && (
            <SectionState isLoading={reportsQuery.isLoading} isError={reportsQuery.isError} error={reportsQuery.error} onRetry={() => reportsQuery.refetch()}>
              {reportsQuery.data &&
                (reportsQuery.data.length === 0 ? (
                  <EmptyState title="No reports generated" description="Nothing to show yet." />
                ) : (
                  <ul className="flex flex-col gap-1.5 text-sm">
                    {reportsQuery.data.map((report) => (
                      <li key={report.id} className="flex justify-between">
                        <span>{report.title}</span>
                        <span className="text-muted-foreground text-xs">
                          {report.status} · {report.rowCount ?? "—"} rows
                        </span>
                      </li>
                    ))}
                  </ul>
                ))}
            </SectionState>
          )}
        </Tabs>
      </CardContent>
    </Card>
  );
}
