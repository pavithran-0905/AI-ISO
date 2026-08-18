import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { NoOrganizationAccessState, OrganizationPicker } from "@/features/dashboard/components/organization-picker";
import { useOrganizationStore } from "@/organization/store";

const ORGS = [
  { id: "org-a", name: "org-a", displayName: "Org A", shortName: null, slug: "org-a", status: "active" },
  { id: "org-b", name: "org-b", displayName: "Org B", shortName: null, slug: "org-b", status: "active" },
];

describe("OrganizationPicker", () => {
  afterEach(() => {
    useOrganizationStore.setState({ selectedOrganizationId: null });
  });

  it("lists every organization the user can pick from", () => {
    render(<OrganizationPicker organizations={ORGS} />);

    expect(screen.getByRole("button", { name: "Org A" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Org B" })).toBeInTheDocument();
  });

  it("selects an organization when clicked", () => {
    render(<OrganizationPicker organizations={ORGS} />);

    fireEvent.click(screen.getByRole("button", { name: "Org B" }));

    expect(useOrganizationStore.getState().selectedOrganizationId).toBe("org-b");
  });
});

describe("NoOrganizationAccessState", () => {
  it("shows an honest no-access message, not fake sample data", () => {
    render(<NoOrganizationAccessState />);
    expect(screen.getByText("No organization access yet")).toBeInTheDocument();
  });
});
