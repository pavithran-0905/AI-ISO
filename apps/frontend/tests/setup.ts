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

// jsdom has no layout engine, so it never implements Element.scrollIntoView
// (used by e.g. the AI Assistant transcript's auto-scroll-to-bottom effect).
// A no-op is sufficient for tests, which only exercise that the call site
// doesn't throw, not real scroll positioning.
if (typeof Element !== "undefined" && !Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = function scrollIntoView() {};
}

afterEach(() => {
  cleanup();
  window.localStorage.clear();
});
