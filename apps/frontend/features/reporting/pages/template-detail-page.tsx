"use client";

import { useRouter } from "next/navigation";

import { PageHeader } from "@/components/navigation/page-header";
import { Button } from "@/components/ui/button";
import { SectionState } from "@/features/dashboard/components/section-state";
import { TemplateDetailView } from "@/features/reporting/components/template-detail-view";
import { useTemplate } from "@/features/reporting/hooks/use-templates";

/** Template Detail — `/reporting/templates/[id]`. Not registered in
 * `lib/route-registry.ts` (dynamic id) — renders its own "Back to
 * Templates" action instead. */
export function TemplateDetailPage({ templateId }: { templateId: string }) {
  const router = useRouter();
  const query = useTemplate(templateId);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={query.data?.name ?? "Template"}
        description={query.data ? `${query.data.category} · v${query.data.versionNumber}` : undefined}
        secondaryActions={
          <Button variant="outline" onClick={() => router.push("/reporting/templates")}>
            Back to Templates
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
        {query.data && <TemplateDetailView template={query.data} />}
      </SectionState>
    </div>
  );
}
