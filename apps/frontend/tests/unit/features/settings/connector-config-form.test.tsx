import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ConnectorConfigForm } from "@/features/settings/components/connector-config-form";
import { useConfigureConnector } from "@/features/settings/hooks/use-integrations";

vi.mock("@/features/settings/hooks/use-integrations", () => ({ useConfigureConnector: vi.fn() }));

describe("ConnectorConfigForm", () => {
  it("masks a sensitive-looking key's value until explicitly revealed", () => {
    vi.mocked(useConfigureConnector).mockReturnValue({ mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof useConfigureConnector>);
    render(<ConnectorConfigForm connectorId="c1" config={{ api_key: "sk-should-not-render-raw", endpoint_url: "https://example.com" }} />);

    expect(screen.getByText("••••••••")).toBeInTheDocument();
    expect(screen.queryByDisplayValue(/sk-should-not-render-raw/)).not.toBeInTheDocument();
    expect(screen.getByDisplayValue("https://example.com")).toBeInTheDocument();
  });

  it("submits an added key/value field as part of the full config replace", async () => {
    const mutateAsync = vi.fn().mockResolvedValue({});
    vi.mocked(useConfigureConnector).mockReturnValue({ mutateAsync, isPending: false } as unknown as ReturnType<typeof useConfigureConnector>);

    render(<ConnectorConfigForm connectorId="c1" config={{ host: "10.0.0.1" }} />);
    fireEvent.click(screen.getByRole("button", { name: "Add field" }));
    const keyInputs = screen.getAllByLabelText("Key");
    const valueInputs = screen.getAllByLabelText("Value");
    fireEvent.change(keyInputs[1], { target: { value: "port" } });
    fireEvent.change(valueInputs[1], { target: { value: "443" } });
    fireEvent.click(screen.getByRole("button", { name: "Save configuration" }));

    await vi.waitFor(() => expect(mutateAsync).toHaveBeenCalledWith({ config: { host: "10.0.0.1", port: "443" } }));
  });
});
