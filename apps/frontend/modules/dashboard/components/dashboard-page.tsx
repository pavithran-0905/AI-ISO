import { typography } from "@/lib/typography";
import { cn } from "@/utils/cn";

import { HealthStatusCard } from "./health-status-card";

export function DashboardPage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className={typography.pageTitle}>Dashboard</h1>
        <p className={cn(typography.body, "text-muted-foreground")}>
          Platform foundation is running. Business modules are not yet implemented.
        </p>
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <HealthStatusCard />
      </div>
    </div>
  );
}
