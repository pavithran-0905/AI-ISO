"use client";

import { useEffect, type RefObject } from "react";

/**
 * Shared close-on-outside-click / close-on-Escape behavior for
 * click-triggered overlays that aren't built on native `<dialog>`
 * (`Popover`, `Dropdown`) — `Dialog`/`Drawer` get this for free from
 * `showModal()` instead; this hook exists specifically for the
 * lighter-weight overlays that don't warrant a full modal.
 */
export function useDismissableLayer(open: boolean, ref: RefObject<HTMLElement | null>, onClose: () => void): void {
  useEffect(() => {
    if (!open) return;

    function handlePointerDown(event: PointerEvent) {
      if (ref.current && event.target instanceof Node && !ref.current.contains(event.target)) {
        onClose();
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open, ref, onClose]);
}
