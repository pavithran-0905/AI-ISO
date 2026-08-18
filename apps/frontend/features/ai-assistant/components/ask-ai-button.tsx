import { Sparkles } from "lucide-react";
import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/utils/cn";

/**
 * The cross-module "Ask AI" entry point (§41). Always opens a new
 * conversation with a pre-filled but **not auto-sent** draft message
 * referencing the real entity's real name/id in plain text — the only
 * honest mechanism available, since no structured context-attachment
 * API exists on this backend (see
 * `docs/frontend/backend-v1-integration-limitations.md`). Never
 * fabricates a context payload the assistant doesn't actually receive.
 */
export function AskAiButton({ draft = "", className }: { draft?: string; className?: string }) {
  const href = draft ? `/intelligence/assistant?draft=${encodeURIComponent(draft)}` : "/intelligence/assistant";
  return (
    <Link href={href} className={cn(buttonVariants("outline", "gap-1.5"), className)}>
      <Sparkles className="size-4" aria-hidden="true" />
      Ask AI
    </Link>
  );
}
