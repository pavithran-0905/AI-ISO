"use client";

import Link from "next/link";

import { Card, CardContent } from "@/components/data-display/card";
import { EmptyState } from "@/components/feedback/empty-state";
import { StatusBadge } from "@/components/feedback/status-badge";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useTemplateVersions } from "@/features/reporting/hooks/use-templates";
import { TEMPLATE_STATUS_TONE } from "@/features/reporting/lib/status-tones";

/** `GET /reports/templates/{id}/versions` (§7) — every version sharing
 * this template's `name`, not just this one row's own history. */
export function TemplateVersionsList({ templateId }: { templateId: string }) {
  const query = useTemplateVersions(templateId);

  return (
    <SectionState isLoading={query.isLoading} isError={query.isError} error={query.error} onRetry={() => query.refetch()}>
      {query.data &&
        (query.data.length === 0 ? (
          <EmptyState title="No other versions" description="This is the only version of this template." />
        ) : (
          <ul className="flex flex-col gap-2">
            {query.data.map((version) => (
              <li key={version.id}>
                <Link href={`/reporting/templates/${version.id}`} className="block">
                  <Card className={version.id === templateId ? "border-primary" : "hover:border-muted-foreground/50 transition-colors"}>
                    <CardContent className="flex items-center justify-between gap-3 p-3">
                      <p className="text-sm font-medium">v{version.versionNumber}{version.id === templateId ? " (viewing)" : ""}</p>
                      <StatusBadge tone={TEMPLATE_STATUS_TONE[version.status]} label={version.status} />
                    </CardContent>
                  </Card>
                </Link>
              </li>
            ))}
          </ul>
        ))}
    </SectionState>
  );
}
