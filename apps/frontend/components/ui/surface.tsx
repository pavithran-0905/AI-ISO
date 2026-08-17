import type { HTMLAttributes } from "react";

import { cn } from "@/utils/cn";

export type SurfaceElevation = "flat" | "raised" | "overlay";

const ELEVATION_CLASSES: Record<SurfaceElevation, string> = {
  /** The default — a bordered panel, no shadow. Prefer this; see
   * docs/frontend/design-system/elevation.md on why elevation is used
   * sparingly. */
  flat: "border border-border bg-surface",
  /** A panel that should read as sitting slightly above the page (a
   * toolbar, a sticky header) without being a full overlay. */
  raised: "border border-border bg-surface-elevated shadow-elevation-1",
  /** A floating layer above the page content — the base a `Popover`/
   * `Dropdown`/`Tooltip` panel builds on. */
  overlay: "border border-border bg-surface-elevated shadow-elevation-3",
};

/**
 * The generic panel primitive (§12) — `Card` (a titled, padded
 * content block) is built for a specific shape; `Surface` is for
 * anything else that needs a bordered/elevated background (a toolbar,
 * a custom panel, the base of an overlay) without `Card`'s own
 * header/content structure.
 */
export function Surface({
  elevation = "flat",
  className,
  ...props
}: HTMLAttributes<HTMLDivElement> & { elevation?: SurfaceElevation }) {
  return <div className={cn("rounded-lg", ELEVATION_CLASSES[elevation], className)} {...props} />;
}
