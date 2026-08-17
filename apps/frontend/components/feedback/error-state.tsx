import { AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/utils/cn";

/** The reusable Error primitive (docs/frontend Prompt 001 §19), also
 * used for the "Retry" state via the optional `onRetry` — a dedicated
 * retry-only component would just be this with `onRetry` set, so the
 * prompt's two named states share one implementation. */
export function ErrorState({
  title = "Something went wrong",
  description,
  onRetry,
  className,
}: {
  title?: string;
  description?: string;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <div
      role="alert"
      className={cn("flex flex-col items-center justify-center gap-3 p-8 text-center", className)}
    >
      <AlertTriangle className="text-danger size-8" aria-hidden="true" />
      <div className="flex flex-col gap-1">
        <p className="text-sm font-medium">{title}</p>
        {description && <p className="text-muted-foreground text-sm">{description}</p>}
      </div>
      {onRetry && (
        <Button variant="outline" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}
