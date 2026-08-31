"use client";

import Link from "next/link";

import { StatusBadge } from "@/components/feedback/status-badge";
import { StatusIndicator } from "@/components/data-display/status-indicator";
import { buttonVariants } from "@/components/ui/button";
import { ResourceSection } from "@/components/resource/resource-section";
import { AskAiButton } from "@/features/ai-assistant/components/ask-ai-button";
import { EXECUTION_STATUS_TO_STATUS } from "@/features/automation/lib/status-maps";
import { splitExecutionVariables } from "@/features/automation/lib/execution-variables";
import type { AutomationExecution } from "@/features/automation/types";

/**
 * §18's Automation context, for a selected execution. Target ids
 * (`splitExecutionVariables`, Prompt 009) are shown as plain, unlinked
 * identifiers — the same treatment `ExecutionDetailView` already
 * established, not changed here: they are real values this execution
 * carried, but this frontend has never confirmed they correspond to a
 * currently-existing `inventory-service` asset (no run-automation form
 * in this codebase populates them from a validated asset picker), so
 * linking them as if verified would overstate what's known.
 */
export function ExecutionContextPanel({ execution }: { execution: AutomationExecution }) {
  const { targetIds } = splitExecutionVariables(execution);

  return (
    <div className="flex flex-col gap-4">
      <ResourceSection title="Execution">
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-2">
            <StatusIndicator state={EXECUTION_STATUS_TO_STATUS[execution.status]} />
            <StatusBadge tone="neutral" label={execution.executionMode} />
          </div>
          <p className="text-sm font-medium">Run {execution.id.slice(0, 8)}</p>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
            <div>
              <dt className="text-muted-foreground">Started</dt>
              <dd>{execution.startedAt ? new Date(execution.startedAt).toLocaleString() : "Not started"}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Completed</dt>
              <dd>{execution.completedAt ? new Date(execution.completedAt).toLocaleString() : "In progress"}</dd>
            </div>
          </dl>
          {execution.errorMessage && <p className="text-danger text-xs">{execution.errorMessage}</p>}
          <div className="flex flex-wrap gap-2">
            <Link href={`/automation/executions/${execution.id}`} className={buttonVariants("outline")}>
              Open Execution
            </Link>
            <AskAiButton
              draft={`Investigate this automation run (id: ${execution.id}), status ${execution.status}${execution.errorMessage ? `, error: ${execution.errorMessage}` : ""}.`}
            />
          </div>
        </div>
      </ResourceSection>

      <ResourceSection title="Targets">
        {targetIds.length === 0 ? (
          <p className="text-muted-foreground text-sm">No targets — this run executed on the AI-IOS automation host.</p>
        ) : (
          <ul className="flex flex-col gap-1">
            {targetIds.map((targetId) => (
              <li key={targetId} className="font-mono text-xs">
                {targetId}
              </li>
            ))}
          </ul>
        )}
      </ResourceSection>
    </div>
  );
}
