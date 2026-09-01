"use client";

import { Settings2 } from "lucide-react";
import { useState } from "react";

import { Popover } from "@/components/overlays/popover";
import { IconButton } from "@/components/ui/icon-button";
import { DASHBOARD_WIDGET_REGISTRY } from "@/features/dashboard/lib/widget-registry";
import { useDashboardPreferencesStore } from "@/state/dashboard-preferences-store";

/**
 * §24's personalization surface — toggle any *optional* widget's
 * visibility, persisted locally (`useDashboardPreferencesStore`). The
 * six foundational sections aren't listed here since they aren't
 * optional — see the registry's own docstring for why.
 */
export function DashboardCustomizeMenu() {
  const [open, setOpen] = useState(false);
  const hiddenWidgetIds = useDashboardPreferencesStore((state) => state.hiddenWidgetIds);
  const toggleWidget = useDashboardPreferencesStore((state) => state.toggleWidget);

  return (
    <Popover
      open={open}
      onClose={() => setOpen(false)}
      align="end"
      trigger={
        <IconButton icon={Settings2} aria-label="Customize dashboard" variant="outline" onClick={() => setOpen((value) => !value)} />
      }
    >
      <fieldset className="flex w-56 flex-col gap-2">
        <legend className="mb-1 text-xs font-semibold">Widgets</legend>
        {DASHBOARD_WIDGET_REGISTRY.map((widget) => (
          <label key={widget.id} className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={!hiddenWidgetIds.includes(widget.id)}
              onChange={() => toggleWidget(widget.id)}
              className="accent-primary size-4"
            />
            {widget.title}
          </label>
        ))}
      </fieldset>
    </Popover>
  );
}
