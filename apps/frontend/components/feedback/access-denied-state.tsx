import { Lock, ShieldAlert } from "lucide-react";

import { cn } from "@/utils/cn";

export type AccessDeniedVariant = "unauthorized" | "forbidden";

const COPY: Record<AccessDeniedVariant, { title: string; description: string; icon: typeof Lock }> = {
  unauthorized: {
    title: "Sign in required",
    description: "Your session has expired or you haven't signed in yet.",
    icon: Lock,
  },
  forbidden: {
    title: "Access denied",
    description: "Your account doesn't have permission to view this page.",
    icon: ShieldAlert,
  },
};

/** The reusable Unauthorized (401) / Forbidden (403) primitives
 * (docs/frontend Prompt 001 §19) — one component parameterized by
 * `variant`, since the two states are visually near-identical and a
 * second near-duplicate component would just be copy-pasted markup. */
export function AccessDeniedState({
  variant,
  action,
  className,
}: {
  variant: AccessDeniedVariant;
  action?: React.ReactNode;
  className?: string;
}) {
  const { title, description, icon: Icon } = COPY[variant];
  return (
    <div
      role="alert"
      className={cn("flex flex-col items-center justify-center gap-3 p-8 text-center", className)}
    >
      <Icon className="text-muted-foreground size-8" aria-hidden="true" />
      <div className="flex flex-col gap-1">
        <p className="text-sm font-medium">{title}</p>
        <p className="text-muted-foreground text-sm">{description}</p>
      </div>
      {action}
    </div>
  );
}
