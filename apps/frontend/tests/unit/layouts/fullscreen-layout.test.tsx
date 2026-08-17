import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FullscreenLayout } from "@/layouts/fullscreen-layout";

describe("FullscreenLayout", () => {
  it("renders an optional top bar and children", () => {
    render(
      <FullscreenLayout topBar={<div>exit</div>}>
        <p>workspace content</p>
      </FullscreenLayout>,
    );

    expect(screen.getByText("exit")).toBeInTheDocument();
    expect(screen.getByText("workspace content")).toBeInTheDocument();
  });

  it("renders without a top bar", () => {
    render(
      <FullscreenLayout>
        <p>workspace content</p>
      </FullscreenLayout>,
    );

    expect(screen.getByText("workspace content")).toBeInTheDocument();
  });
});
