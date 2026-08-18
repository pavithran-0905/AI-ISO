import Link from "next/link";

import { Card, CardContent } from "@/components/data-display/card";
import { typography } from "@/lib/typography";
import { cn } from "@/utils/cn";

/**
 * The reusable KPI tile (docs/frontend Prompt 005 §7). Deliberately has
 * no `trend`/`change` prop — the backend doesn't provide enough
 * historical data to compute one correctly (`OrganizationStatisticsResponse`
 * is a snapshot, not a series), and §7 explicitly forbids a fabricated
 * "+24%".
 */
export function MetricCard({
  label,
  value,
  description,
  href,
  className,
}: {
  label: string;
  value: string | number;
  description?: string;
  /** A real, existing route only — the caller is responsible for that
   * (§26: "only link to routes that actually exist"). Omit when no
   * matching page exists yet. */
  href?: string;
  className?: string;
}) {
  const content = (
    <CardContent className="flex flex-col gap-1 p-4">
      <p className={cn(typography.caption, "text-muted-foreground")}>{label}</p>
      <p className="text-2xl font-semibold tabular-nums">{value}</p>
      {description && <p className="text-muted-foreground text-xs">{description}</p>}
    </CardContent>
  );

  if (href) {
    return (
      <Link href={href} className="block focus-visible:ring-ring rounded-lg focus-visible:ring-2 focus-visible:outline-none">
        <Card className={cn("hover:border-muted-foreground/50 transition-colors", className)}>{content}</Card>
      </Link>
    );
  }

  return <Card className={className}>{content}</Card>;
}
