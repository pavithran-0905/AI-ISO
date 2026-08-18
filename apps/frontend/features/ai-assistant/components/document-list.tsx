"use client";

import { FileText } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/feedback/empty-state";
import { Skeleton } from "@/components/feedback/skeleton";
import { useKnowledgeDocuments } from "@/features/ai-assistant/hooks/use-knowledge";

/** Every document ingested for retrieval, for this organization. */
export function DocumentList({ organizationId }: { organizationId: string }) {
  const documentsQuery = useKnowledgeDocuments(organizationId);

  if (documentsQuery.isLoading) {
    return (
      <div className="flex flex-col gap-2" role="status" aria-label="Loading documents">
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-12 w-full" />
      </div>
    );
  }

  if (documentsQuery.isError) {
    return <p className="text-danger text-sm">Documents could not be loaded.</p>;
  }

  if (!documentsQuery.data || documentsQuery.data.length === 0) {
    return <EmptyState icon={FileText} title="No documents ingested" description="Ingest a document below to make it retrievable." />;
  }

  return (
    <ul className="divide-border border-border divide-y rounded-md border">
      {documentsQuery.data.map((document) => (
        <li key={document.id} className="flex items-center justify-between gap-3 p-3 text-sm">
          <div className="flex min-w-0 flex-col gap-0.5">
            <span className="truncate font-medium">{document.title}</span>
            {document.uri && (
              <a href={document.uri} target="_blank" rel="noreferrer" className="text-primary truncate text-xs hover:underline">
                {document.uri}
              </a>
            )}
          </div>
          <Badge variant="outline" className="shrink-0">
            {document.sourceType}
          </Badge>
        </li>
      ))}
    </ul>
  );
}
