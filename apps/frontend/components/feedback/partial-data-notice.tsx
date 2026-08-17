import { AlertCircle } from "lucide-react";

import { cn } from "@/utils/cn";

/** The reusable Partial Data primitive (docs/frontend Prompt 001 §19) —
 * an inline banner for when a response returns *some* usable data
 * alongside a partial failure (e.g. 3 of 4 requested regions), so the
 * feature can render what it has instead of an all-or-nothing
 * `ErrorState`. */
export function PartialDataNotice({ message, className }: { message: string; className?: string }) {
  return (
    <div
      role="status"
      className={cn(
        "border-warning/30 bg-warning/10 text-warning-foreground flex items-center gap-2 rounded-md border px-3 py-2 text-sm",
        className,
      )}
    >
      <AlertCircle className="size-4 shrink-0" aria-hidden="true" />
      <span>{message}</span>
    </div>
  );
}
