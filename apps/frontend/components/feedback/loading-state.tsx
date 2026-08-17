import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/utils/cn";

/** The reusable Loading primitive (docs/frontend Prompt 001 §19) — every
 * feature awaiting async data renders this instead of inventing its own
 * spinner markup. Composes `Spinner` (§12 of Prompt 002) rather than
 * its own `Loader2` usage, so every loading indicator in the app is the
 * same glyph at the same weight. */
export function LoadingState({ label = "Loading…", className }: { label?: string; className?: string }) {
  return (
    <div
      role="status"
      className={cn("text-muted-foreground flex flex-col items-center justify-center gap-2 p-8 text-sm", className)}
    >
      <Spinner size="control" />
      <span>{label}</span>
    </div>
  );
}
