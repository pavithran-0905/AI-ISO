import { Loader2 } from "lucide-react";

import { iconSize, type IconSizeToken } from "@/lib/icons";
import { cn } from "@/utils/cn";

/**
 * The bare spinning-glyph primitive (§12) — for inline/small loading
 * signals (inside a `Button`, next to a label). For a standalone
 * loading region with its own message, use `LoadingState` instead,
 * which composes this.
 */
export function Spinner({ size = "control", className }: { size?: IconSizeToken; className?: string }) {
  return (
    <Loader2
      className={cn(iconSize[size], "animate-spin motion-reduce:animate-none", className)}
      aria-hidden="true"
    />
  );
}
