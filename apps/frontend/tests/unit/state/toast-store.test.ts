import { afterEach, describe, expect, it, vi } from "vitest";

import { toast, useToastStore } from "@/state/toast-store";

describe("toast", () => {
  afterEach(() => {
    useToastStore.setState({ toasts: [] });
    vi.useRealTimers();
  });

  it("pushes a toast with the given tone/title/description", () => {
    toast.success("Saved", "Your changes were saved.");
    const [item] = useToastStore.getState().toasts;
    expect(item).toMatchObject({ tone: "success", title: "Saved", description: "Your changes were saved." });
  });

  it("each toast kind pushes its own tone", () => {
    toast.info("i");
    toast.warning("w");
    toast.danger("d");
    const tones = useToastStore.getState().toasts.map((item) => item.tone);
    expect(tones).toEqual(["info", "warning", "danger"]);
  });

  it("auto-dismisses after the default duration", () => {
    vi.useFakeTimers();
    toast.info("Will vanish");
    expect(useToastStore.getState().toasts).toHaveLength(1);

    vi.advanceTimersByTime(5000);
    expect(useToastStore.getState().toasts).toHaveLength(0);
  });

  it("dismiss removes a specific toast by id", () => {
    toast.info("first");
    toast.info("second");
    const [first] = useToastStore.getState().toasts;

    useToastStore.getState().dismiss(first.id);

    const remaining = useToastStore.getState().toasts;
    expect(remaining).toHaveLength(1);
    expect(remaining[0].title).toBe("second");
  });
});
