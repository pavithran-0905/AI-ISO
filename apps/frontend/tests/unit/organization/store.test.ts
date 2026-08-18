import { afterEach, describe, expect, it } from "vitest";

import { useOrganizationStore } from "@/organization/store";

describe("useOrganizationStore", () => {
  afterEach(() => {
    useOrganizationStore.setState({ selectedOrganizationId: null });
  });

  it("starts with no organization selected", () => {
    expect(useOrganizationStore.getState().selectedOrganizationId).toBeNull();
  });

  it("setSelectedOrganizationId() sets and clears the selection", () => {
    useOrganizationStore.getState().setSelectedOrganizationId("org-1");
    expect(useOrganizationStore.getState().selectedOrganizationId).toBe("org-1");

    useOrganizationStore.getState().setSelectedOrganizationId(null);
    expect(useOrganizationStore.getState().selectedOrganizationId).toBeNull();
  });
});
