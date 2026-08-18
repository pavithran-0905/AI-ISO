"use client";

import { Check, Copy, Search } from "lucide-react";
import { useMemo, useState } from "react";

import { EmptyState } from "@/components/feedback/empty-state";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/forms/input";
import { Label } from "@/components/forms/label";
import { Select } from "@/components/forms/select";
import { StatusBadge } from "@/components/feedback/status-badge";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useExecutionLogs } from "@/features/automation/hooks/use-executions";
import { LOG_LEVEL_TONE } from "@/features/automation/lib/status-maps";
import { LOG_LEVELS, type LogLevelValue } from "@/features/automation/types";

/**
 * The execution log viewer (§17). Real capabilities only:
 *
 * - Timestamps and severity: both real fields on
 *   `AutomationExecutionLogResponse`.
 * - Search and level filter: applied client-side, honestly — the logs
 *   endpoint takes no params at all and returns the complete log every
 *   call, so nothing is hidden behind a page boundary.
 * - Copy: real.
 *
 * Deliberately absent: follow/pause-streaming controls and auto-scroll.
 * §17 asks for them "if streaming exists" — it doesn't.
 * `automation-service` exposes no WebSocket or SSE endpoint anywhere
 * (confirmed by source inspection), so this polls while the run is
 * active and stops when it finishes. A "pause following" control over
 * a poll would be theatre.
 *
 * Note each entry is one truncated stdout/stderr blob per execution
 * step, not line-by-line console output — the viewer presents them as
 * blocks rather than pretending to be a terminal.
 */
export function ExecutionLogViewer({ executionId, isActive }: { executionId: string; isActive: boolean }) {
  const query = useExecutionLogs(executionId, isActive);
  const [search, setSearch] = useState("");
  const [level, setLevel] = useState<LogLevelValue | "">("");
  const [copied, setCopied] = useState(false);

  const visibleLogs = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return (query.data ?? []).filter(
      (log) => (!level || log.level === level) && (!needle || log.message.toLowerCase().includes(needle)),
    );
  }, [query.data, search, level]);

  async function handleCopy() {
    await navigator.clipboard.writeText(visibleLogs.map((log) => `[${log.loggedAt}] ${log.level.toUpperCase()}: ${log.message}`).join("\n\n"));
    setCopied(true);
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex min-w-48 flex-1 flex-col gap-1.5">
          <Label htmlFor="log-search">Search output</Label>
          <div className="relative">
            <Search className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2" aria-hidden="true" />
            <Input id="log-search" value={search} onChange={(event) => setSearch(event.target.value)} className="pl-9" />
          </div>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="log-level">Level</Label>
          <Select id="log-level" value={level} onChange={(event) => setLevel(event.target.value as LogLevelValue | "")} className="w-32">
            <option value="">All levels</option>
            {LOG_LEVELS.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </Select>
        </div>
        {visibleLogs.length > 0 && (
          <Button variant="outline" onClick={handleCopy} className="gap-1.5">
            {copied ? <Check className="size-4" aria-hidden="true" /> : <Copy className="size-4" aria-hidden="true" />}
            {copied ? "Copied" : "Copy output"}
          </Button>
        )}
      </div>

      <SectionState isLoading={query.isLoading} isError={query.isError} error={query.error} onRetry={() => query.refetch()}>
        {query.data &&
          (visibleLogs.length === 0 ? (
            <EmptyState
              title={query.data.length === 0 ? "No execution logs available" : "No matching log entries"}
              description={
                query.data.length === 0
                  ? isActive
                    ? "This run hasn't produced any output yet."
                    : "This run finished without recording any output."
                  : "Try a different search term or level."
              }
            />
          ) : (
            <ul className="flex flex-col gap-2">
              {visibleLogs.map((log) => (
                <li key={log.id}>
                  <div className="border-border flex flex-col gap-2 rounded-md border p-3">
                    <div className="flex items-center gap-2">
                      <StatusBadge tone={LOG_LEVEL_TONE[log.level]} label={log.level} />
                      <time dateTime={log.loggedAt} className="text-muted-foreground text-xs">
                        {new Date(log.loggedAt).toLocaleString()}
                      </time>
                    </div>
                    <pre className="overflow-x-auto text-xs whitespace-pre-wrap">{log.message}</pre>
                  </div>
                </li>
              ))}
            </ul>
          ))}
      </SectionState>

      {isActive && <p className="text-muted-foreground text-xs">Following this run — output refreshes automatically.</p>}
    </div>
  );
}
