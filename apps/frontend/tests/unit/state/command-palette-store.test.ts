import { afterEach, describe, expect, it } from "vitest";

import { useCommandPaletteStore } from "@/state/command-palette-store";

describe("useCommandPaletteStore", () => {
  afterEach(() => {
    useCommandPaletteStore.setState({ open: false });
  });

  it("starts closed", () => {
    expect(useCommandPaletteStore.getState().open).toBe(false);
  });

  it("show() opens and hide() closes", () => {
    useCommandPaletteStore.getState().show();
    expect(useCommandPaletteStore.getState().open).toBe(true);

    useCommandPaletteStore.getState().hide();
    expect(useCommandPaletteStore.getState().open).toBe(false);
  });

  it("toggle() flips open", () => {
    useCommandPaletteStore.getState().toggle();
    expect(useCommandPaletteStore.getState().open).toBe(true);

    useCommandPaletteStore.getState().toggle();
    expect(useCommandPaletteStore.getState().open).toBe(false);
  });
});
