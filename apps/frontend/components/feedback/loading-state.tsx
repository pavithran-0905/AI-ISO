import { Loader2 } from "lucide-react";

import { cn } from "@/utils/cn";

/** The reusable Loading primitive (docs/frontend Prompt 001 §19) — every
 * feature awaiting async data renders this instead of inventing its own
 * spinner markup. */
export function LoadingState({ label = "Loading…", className }: { label?: string; className?: string }) {
  return (
    <div
      role="status"
      className={cn("text-muted-foreground flex flex-col items-center justify-center gap-2 p-8 text-sm", className)}
    >
      <Loader2 className="size-5 animate-spin motion-reduce:animate-none" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}
