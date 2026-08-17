import { cn } from "@/utils/cn";

/** The reusable Skeleton primitive (docs/frontend Prompt 001 §19).
 * `aria-hidden`: a skeleton is a purely visual loading placeholder: the
 * surrounding `LoadingState`/`role="status"` region (or the eventual
 * real content) is what screen readers should announce, not this. */
export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden="true" className={cn("bg-muted animate-pulse rounded-md motion-reduce:animate-none", className)} />;
}
