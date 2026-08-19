import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApiKeysSection } from "@/features/settings/components/api-keys-section";
import { useApiKeys, useCreateApiKey, useRevokeApiKey } from "@/features/settings/hooks/use-security";

vi.mock("@/features/settings/hooks/use-security", () => ({
  useApiKeys: vi.fn(),
  useCreateApiKey: vi.fn(),
  useRevokeApiKey: vi.fn(),
}));

describe("ApiKeysSection", () => {
  it("reveals the raw key exactly once after creation, in a dedicated dialog", async () => {
    vi.mocked(useApiKeys).mockReturnValue({ data: [], isLoading: false, isError: false, refetch: vi.fn() } as unknown as ReturnType<typeof useApiKeys>);
    const createApiKey = vi.fn().mockResolvedValue({
      id: "k1",
      name: "CI key",
      keyPrefix: "aiios_ab12",
      scopes: [],
      expiresAt: null,
      lastUsedAt: null,
      revokedAt: null,
      rawKey: "aiios_ab12_the_full_secret_value",
    });
    vi.mocked(useCreateApiKey).mockReturnValue({ mutateAsync: createApiKey, isPending: false } as unknown as ReturnType<typeof useCreateApiKey>);
    vi.mocked(useRevokeApiKey).mockReturnValue({ mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof useRevokeApiKey>);

    render(<ApiKeysSection />);
    fireEvent.click(screen.getByRole("button", { name: "Create API key" }));
    fireEvent.change(screen.getByLabelText("Name*"), { target: { value: "CI key" } });
    fireEvent.click(screen.getByRole("button", { name: "Create key" }));

    await vi.waitFor(() => expect(screen.getByText("aiios_ab12_the_full_secret_value")).toBeInTheDocument());
    expect(createApiKey).toHaveBeenCalledWith({ name: "CI key", scopes: [] });
  });

  it("lets a non-revoked key be revoked", async () => {
    vi.mocked(useApiKeys).mockReturnValue({
      data: [{ id: "k1", name: "CI key", keyPrefix: "aiios_ab12", scopes: [], expiresAt: null, lastUsedAt: null, revokedAt: null }],
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useApiKeys>);
    vi.mocked(useCreateApiKey).mockReturnValue({ mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof useCreateApiKey>);
    const revokeApiKey = vi.fn().mockResolvedValue(undefined);
    vi.mocked(useRevokeApiKey).mockReturnValue({ mutateAsync: revokeApiKey, isPending: false } as unknown as ReturnType<typeof useRevokeApiKey>);

    render(<ApiKeysSection />);
    fireEvent.click(screen.getByRole("button", { name: "Revoke CI key" }));

    await vi.waitFor(() => expect(revokeApiKey).toHaveBeenCalledWith("k1"));
  });
});
