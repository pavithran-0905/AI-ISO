import { ArrowRight } from "lucide-react";

import { StatusIndicator } from "@/components/data-display/status-indicator";
import { ASSET_HEALTH_STATUSES } from "@/features/infrastructure/types";
import { ASSET_HEALTH_TO_STATUS } from "@/features/infrastructure/lib/status-maps";

/**
 * §25: every meaning here is carried by an icon and a text label, not
 * colour alone — the same rule `StatusIndicator` already follows
 * everywhere else in this app.
 */
export function TopologyLegend() {
  return (
    <div className="flex flex-col gap-3 text-xs">
      <div>
        <p className="text-muted-foreground mb-1.5 font-medium">Health</p>
        <div className="flex flex-col gap-1">
          {ASSET_HEALTH_STATUSES.map((health) => (
            <StatusIndicator key={health} state={ASSET_HEALTH_TO_STATUS[health]} label={health} />
          ))}
        </div>
      </div>
      <div>
        <p className="text-muted-foreground mb-1.5 font-medium">Node</p>
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center gap-2">
            <span className="border-primary ring-primary/30 size-3 rounded border ring-2" aria-hidden="true" />
            <span>Focused asset</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="border-border size-3 rounded border" aria-hidden="true" />
            <span>Direct relationship</span>
          </div>
        </div>
      </div>
      <div>
        <p className="text-muted-foreground mb-1.5 font-medium">Relationship</p>
        <div className="flex items-center gap-2">
          <ArrowRight className="size-3.5" aria-hidden="true" />
          <span>Points from source to target</span>
        </div>
      </div>
    </div>
  );
}
