import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AssetCreateForm } from "@/features/infrastructure/components/asset-create-form";

describe("AssetCreateForm", () => {
  it("requires a name and an asset type before submitting", () => {
    const onSubmit = vi.fn();
    const { container } = render(<AssetCreateForm organizationId="org-1" onSubmit={onSubmit} isSubmitting={false} />);

    // Dispatched directly on the form (bypassing the native `required`
    // constraint validation a real button click would trigger first)
    // to exercise this component's own validation message.
    fireEvent.submit(container.querySelector("form") as HTMLFormElement);

    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByText("Name and asset type are required.")).toBeInTheDocument();
  });

  it("submits real AssetCreateRequest fields, trimmed, with empty optional fields omitted", () => {
    const onSubmit = vi.fn();
    render(<AssetCreateForm organizationId="org-1" onSubmit={onSubmit} isSubmitting={false} />);

    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "  web-01  " } });
    fireEvent.change(screen.getByLabelText("Type"), { target: { value: "virtual_machine" } });
    fireEvent.click(screen.getByRole("button", { name: "Register asset" }));

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        organizationId: "org-1",
        name: "web-01",
        assetType: "virtual_machine",
        criticality: "medium",
        tags: [],
        hostname: undefined,
      }),
    );
  });

  it("parses a comma-separated tags field into a real string array", () => {
    const onSubmit = vi.fn();
    render(<AssetCreateForm organizationId="org-1" onSubmit={onSubmit} isSubmitting={false} />);

    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "web-01" } });
    fireEvent.change(screen.getByLabelText("Type"), { target: { value: "virtual_machine" } });
    fireEvent.change(screen.getByLabelText("Tags (comma-separated)"), { target: { value: "prod, tier-1,  edge " } });
    fireEvent.click(screen.getByRole("button", { name: "Register asset" }));

    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ tags: ["prod", "tier-1", "edge"] }));
  });
});
