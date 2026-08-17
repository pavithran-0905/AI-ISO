"use client";

import { useCallback, useRef, useState } from "react";

import { cn } from "@/utils/cn";

const DEFAULT_MIN_PANE_PERCENT = 20;

/**
 * Split-Pane Workspace Layout (docs/frontend Prompt 001 §16) — a
 * resizable two-pane view (e.g. a future list/detail or editor/preview
 * screen). Falls back to a stacked layout below `md` per §21's
 * responsive requirement ("split-pane fallback") rather than shrinking
 * two side-by-side panes into uselessness.
 */
export function SplitPaneLayout({
  start,
  end,
  defaultSplitPercent = 40,
  minPanePercent = DEFAULT_MIN_PANE_PERCENT,
}: {
  start: React.ReactNode;
  end: React.ReactNode;
  defaultSplitPercent?: number;
  minPanePercent?: number;
}) {
  const [splitPercent, setSplitPercent] = useState(defaultSplitPercent);
  const containerRef = useRef<HTMLDivElement>(null);
  const draggingRef = useRef(false);

  const clamp = useCallback(
    (value: number) => Math.min(100 - minPanePercent, Math.max(minPanePercent, value)),
    [minPanePercent],
  );

  /** Both listeners are declared and paired within this single closure
   * (rather than as separate stable callbacks) so `onPointerUp` can
   * remove them without needing a stable reference to itself across
   * renders. */
  const startDragging = useCallback(() => {
    draggingRef.current = true;

    function onPointerMove(event: PointerEvent) {
      if (!draggingRef.current || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const percent = ((event.clientX - rect.left) / rect.width) * 100;
      setSplitPercent(clamp(percent));
    }

    function onPointerUp() {
      draggingRef.current = false;
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
    }

    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
  }, [clamp]);

  return (
    <div ref={containerRef} className="flex h-full flex-col md:flex-row">
      <div className="min-h-0 overflow-auto md:h-full" style={{ flexBasis: `${splitPercent}%` }}>
        {start}
      </div>
      <div
        role="separator"
        aria-orientation="vertical"
        tabIndex={0}
        onPointerDown={startDragging}
        onKeyDown={(event) => {
          if (event.key === "ArrowLeft") setSplitPercent((value) => clamp(value - 2));
          if (event.key === "ArrowRight") setSplitPercent((value) => clamp(value + 2));
        }}
        className={cn(
          "bg-border hover:bg-ring focus-visible:ring-ring hidden shrink-0 cursor-col-resize",
          "focus-visible:ring-2 focus-visible:outline-none md:block md:w-1",
        )}
      />
      <div className="min-h-0 flex-1 overflow-auto">{end}</div>
    </div>
  );
}
