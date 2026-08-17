import { AlertTriangle, CheckCircle2, Info, XCircle } from "lucide-react";

import { cn } from "@/utils/cn";

export type AlertTone = "info" | "success" | "warning" | "danger";

const TONE_CONFIG: Record<AlertTone, { icon: typeof Info; classes: string }> = {
  info: { icon: Info, classes: "border-info/30 bg-info/10 text-foreground" },
  success: { icon: CheckCircle2, classes: "border-success/30 bg-success/10 text-foreground" },
  warning: { icon: AlertTriangle, classes: "border-warning/30 bg-warning/10 text-foreground" },
  danger: { icon: XCircle, classes: "border-danger/30 bg-danger/10 text-foreground" },
};

/**
 * An inline, persistent banner (§12) — for a message that belongs to
 * the page's own content (a form-level error, a page-level notice).
 * For a transient, dismissable notification, use `Toast` instead.
 */
export function Alert({
  tone = "info",
  title,
  children,
  className,
}: {
  tone?: AlertTone;
  title: string;
  children?: React.ReactNode;
  className?: string;
}) {
  const { icon: Icon, classes } = TONE_CONFIG[tone];
  return (
    <div role={tone === "danger" || tone === "warning" ? "alert" : "status"} className={cn("flex gap-3 rounded-md border p-3 text-sm", classes, className)}>
      <Icon className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <div className="flex flex-col gap-0.5">
        <p className="font-medium">{title}</p>
        {children && <div className="text-muted-foreground">{children}</div>}
      </div>
    </div>
  );
}
