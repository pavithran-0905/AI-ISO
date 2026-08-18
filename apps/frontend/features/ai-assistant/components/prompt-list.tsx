"use client";

import { FileCode } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/feedback/empty-state";
import { Skeleton } from "@/components/feedback/skeleton";
import { usePrompts } from "@/features/ai-assistant/hooks/use-prompts";
import { cn } from "@/utils/cn";

export function PromptList({
  organizationId,
  selectedPromptId,
  onSelect,
}: {
  organizationId: string;
  selectedPromptId: string | null;
  onSelect: (promptId: string) => void;
}) {
  const promptsQuery = usePrompts(organizationId);

  if (promptsQuery.isLoading) {
    return (
      <div className="flex flex-col gap-2" role="status" aria-label="Loading prompts">
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-12 w-full" />
      </div>
    );
  }

  if (promptsQuery.isError) {
    return <p className="text-danger text-sm">Prompts could not be loaded.</p>;
  }

  if (!promptsQuery.data || promptsQuery.data.length === 0) {
    return <EmptyState icon={FileCode} title="No prompts yet" description="Create one to get started." />;
  }

  return (
    <ul className="flex flex-col gap-1">
      {promptsQuery.data.map((prompt) => (
        <li key={prompt.id}>
          <button
            type="button"
            onClick={() => onSelect(prompt.id)}
            aria-current={prompt.id === selectedPromptId ? "true" : undefined}
            className={cn(
              "flex w-full items-center justify-between gap-2 rounded-md border p-2.5 text-left text-sm transition-colors",
              "focus-visible:ring-ring focus-visible:ring-2 focus-visible:outline-none",
              prompt.id === selectedPromptId ? "border-primary bg-primary/5" : "border-transparent hover:bg-muted",
            )}
          >
            <span className="truncate font-medium">{prompt.name}</span>
            <div className="flex shrink-0 items-center gap-1.5">
              <Badge variant="outline">v{prompt.currentVersionNumber}</Badge>
              {!prompt.enabled && <Badge>Disabled</Badge>}
            </div>
          </button>
        </li>
      ))}
    </ul>
  );
}
