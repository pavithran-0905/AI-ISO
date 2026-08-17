import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";

// jsdom does not implement matchMedia. Install a benign default so any
// component touching it doesn't crash; individual tests may override it.
beforeEach(() => {
  window.matchMedia = vi.fn().mockReturnValue({
    matches: false,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  });
});

// jsdom does not implement <dialog>'s showModal()/close() (used by
// Dialog/Drawer, docs/frontend Prompt 002 §12) — polyfill the open/
// close state transition (not full top-layer/focus-trap semantics,
// which jsdom has no rendering engine to provide anyway) so component
// tests can exercise the real open/close prop wiring.
if (typeof HTMLDialogElement !== "undefined") {
  HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
    this.removeAttribute("open");
    this.dispatchEvent(new Event("close"));
  };
}

afterEach(() => {
  cleanup();
  window.localStorage.clear();
});
