import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ConnectionTestPanel } from "@/features/settings/components/connection-test-panel";
import { useTestConnection } from "@/features/settings/hooks/use-integrations";

vi.mock("@/features/settings/hooks/use-integrations", () => ({ useTestConnection: vi.fn() }));

describe("ConnectionTestPanel", () => {
  it("shows a real Success result with latency when the backend made an outbound call", async () => {
    const mutateAsync = vi.fn().mockResolvedValue({
      id: "t1",
      connectorId: "c1",
      credentialId: null,
      status: "success",
      testedAt: "2026-01-01T00:00:00Z",
      latencyMs: 42,
      error: null,
      attemptNumber: 1,
    });
    vi.mocked(useTestConnection).mockReturnValue({ mutateAsync, isPending: false, data: undefined } as unknown as ReturnType<typeof useTestConnection>);

    render(<ConnectionTestPanel connectorId="c1" />);
    fireEvent.click(screen.getByRole("button", { name: "Test connection" }));

    await vi.waitFor(() => expect(mutateAsync).toHaveBeenCalled());
  });

  it("shows the real error message on a Failed result", () => {
    vi.mocked(useTestConnection).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
      data: { id: "t1", connectorId: "c1", credentialId: null, status: "failed", testedAt: "2026-01-01T00:00:00Z", latencyMs: null, error: "Connection refused", attemptNumber: 2 },
    } as unknown as ReturnType<typeof useTestConnection>);

    render(<ConnectionTestPanel connectorId="c1" />);
    expect(screen.getByText("Failed")).toBeInTheDocument();
    expect(screen.getByText("Connection refused")).toBeInTheDocument();
  });

  it("labels a structural-only success (no latency) distinctly from a real network check", () => {
    vi.mocked(useTestConnection).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
      data: { id: "t1", connectorId: "c1", credentialId: null, status: "success", testedAt: "2026-01-01T00:00:00Z", latencyMs: null, error: null, attemptNumber: 1 },
    } as unknown as ReturnType<typeof useTestConnection>);

    render(<ConnectionTestPanel connectorId="c1" />);
    expect(screen.getByText(/Structural check only/)).toBeInTheDocument();
  });
});
