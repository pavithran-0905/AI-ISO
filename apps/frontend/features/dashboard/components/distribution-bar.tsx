import type { StatusTone } from "@/components/feedback/status-badge";
import { cn } from "@/utils/cn";

const TONE_BG: Record<StatusTone, string> = {
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-danger",
  neutral: "bg-muted-foreground/50",
  info: "bg-info",
  pending: "bg-pending",
  running: "bg-running",
  stopped: "bg-stopped",
  degraded: "bg-degraded",
  unknown: "bg-unknown",
};

export interface DistributionSegment {
  key: string;
  label: string;
  value: number;
  tone: StatusTone;
}

/**
 * A compact, accessible horizontal distribution visualization (§11,
 * §39) over real, already-loaded counts — proportionally widthed
 * segments, zero-value segments simply omitted (never a fabricated
 * sliver). Never the sole way the data is conveyed (§40 — "never rely
 * on color alone"): the bar carries one `aria-label` summarizing every
 * segment in a single pass, and a plain-text legend with the same
 * counts sits directly below it, so a screen-reader user and a
 * colorblind user both get the full picture without the bar itself.
 * Renders nothing when there is no data at all — never an empty gray
 * track presented as if it meant something.
 */
export function DistributionBar({ segments, className }: { segments: DistributionSegment[]; className?: string }) {
  const total = segments.reduce((sum, segment) => sum + segment.value, 0);
  const present = segments.filter((segment) => segment.value > 0);
  if (total === 0 || present.length === 0) return null;

  const summary = present.map((segment) => `${segment.label} ${segment.value}`).join(", ");

  return (
    <div className={className}>
      <div
        role="img"
        aria-label={`Distribution: ${summary}, out of ${total} total.`}
        className="bg-muted flex h-3 w-full overflow-hidden rounded-full"
      >
        {present.map((segment) => (
          <span
            key={segment.key}
            aria-hidden="true"
            className={TONE_BG[segment.tone]}
            style={{ width: `${(segment.value / total) * 100}%` }}
          />
        ))}
      </div>
      <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5">
        {present.map((segment) => (
          <li key={segment.key} className="flex items-center gap-1.5 text-xs">
            <span aria-hidden="true" className={cn("size-2 shrink-0 rounded-full", TONE_BG[segment.tone])} />
            <span className="text-muted-foreground">{segment.label}</span>
            <span className="font-medium tabular-nums">{segment.value}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
