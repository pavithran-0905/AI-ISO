import { WifiOff } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/utils/cn";

/** The reusable Offline/Network-Failure primitive (docs/frontend Prompt
 * 001 §19) — distinct from `ErrorState`: this is specifically "the
 * request never reached the backend" (see `ApiNetworkError` in
 * `@/api/client`), not a backend-reported failure. */
export function OfflineState({ onRetry, className }: { onRetry?: () => void; className?: string }) {
  return (
    <div
      role="alert"
      className={cn("flex flex-col items-center justify-center gap-3 p-8 text-center", className)}
    >
      <WifiOff className="text-muted-foreground size-8" aria-hidden="true" />
      <div className="flex flex-col gap-1">
        <p className="text-sm font-medium">You&apos;re offline</p>
        <p className="text-muted-foreground text-sm">Check your connection and try again.</p>
      </div>
      {onRetry && (
        <Button variant="outline" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}
