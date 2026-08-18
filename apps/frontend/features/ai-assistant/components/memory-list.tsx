"use client";

import { BrainCircuit } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/feedback/empty-state";
import { Skeleton } from "@/components/feedback/skeleton";
import { useMemoryEntries } from "@/features/ai-assistant/hooks/use-insights";

/** Read-only: `MemoryResponse` has no delete/clear endpoint despite
 * the prompt's own request for one — see `MemoryEntry`'s own
 * docstring and `docs/frontend/backend-v1-integration-limitations.md`. */
export function MemoryList({ organizationId }: { organizationId: string }) {
  const memoryQuery = useMemoryEntries(organizationId);

  if (memoryQuery.isLoading) {
    return (
      <div className="flex flex-col gap-2" role="status" aria-label="Loading memory">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    );
  }

  if (memoryQuery.isError) {
    return <p className="text-danger text-sm">Memory could not be loaded.</p>;
  }

  if (!memoryQuery.data || memoryQuery.data.length === 0) {
    return <EmptyState icon={BrainCircuit} title="Nothing remembered yet" description="The assistant hasn't stored any facts for this organization." />;
  }

  return (
    <ul className="flex flex-col gap-1.5">
      {memoryQuery.data.map((entry) => (
        <li key={entry.id} className="flex items-start justify-between gap-2 text-sm">
          <div className="flex min-w-0 flex-col">
            <span className="truncate font-medium">{entry.key}</span>
            <span className="text-muted-foreground truncate text-xs">{entry.value}</span>
          </div>
          <Badge variant="outline" className="shrink-0">
            {entry.scope}
          </Badge>
        </li>
      ))}
    </ul>
  );
}
