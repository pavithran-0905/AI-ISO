import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { MfaSection } from "@/features/settings/components/mfa-section";
import { useDisableMfa, useEnableMfa, useVerifyMfa } from "@/features/settings/hooks/use-security";

vi.mock("@/features/settings/hooks/use-security", () => ({
  useEnableMfa: vi.fn(),
  useVerifyMfa: vi.fn(),
  useDisableMfa: vi.fn(),
}));

describe("MfaSection", () => {
  it("shows the secret and recovery codes exactly once after starting enrollment, then hides them on cancel", async () => {
    const enable = vi.fn().mockResolvedValue({ secret: "SECRET123", otpauthUri: "otpauth://totp/x", recoveryCodes: ["code-1", "code-2"] });
    vi.mocked(useEnableMfa).mockReturnValue({ mutateAsync: enable, isPending: false } as unknown as ReturnType<typeof useEnableMfa>);
    vi.mocked(useVerifyMfa).mockReturnValue({ mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof useVerifyMfa>);
    vi.mocked(useDisableMfa).mockReturnValue({ mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof useDisableMfa>);

    render(<MfaSection mfaEnabled={false} />);
    fireEvent.click(screen.getByRole("button", { name: "Enable MFA" }));

    await vi.waitFor(() => expect(screen.getByText("code-1")).toBeInTheDocument());
    expect(screen.getByText(/SECRET123/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByText("code-1")).not.toBeInTheDocument();
  });

  it("verifies with the entered code and confirms enrollment", async () => {
    const enable = vi.fn().mockResolvedValue({ secret: "SECRET123", otpauthUri: "otpauth://totp/x", recoveryCodes: ["code-1"] });
    const verify = vi.fn().mockResolvedValue(undefined);
    vi.mocked(useEnableMfa).mockReturnValue({ mutateAsync: enable, isPending: false } as unknown as ReturnType<typeof useEnableMfa>);
    vi.mocked(useVerifyMfa).mockReturnValue({ mutateAsync: verify, isPending: false } as unknown as ReturnType<typeof useVerifyMfa>);
    vi.mocked(useDisableMfa).mockReturnValue({ mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof useDisableMfa>);

    render(<MfaSection mfaEnabled={false} />);
    fireEvent.click(screen.getByRole("button", { name: "Enable MFA" }));
    await vi.waitFor(() => expect(screen.getByLabelText("Verification code")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Verification code"), { target: { value: "123456" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirm and enable" }));

    await vi.waitFor(() => expect(verify).toHaveBeenCalledWith("123456"));
  });

  it("requires a code to disable MFA when already enabled", async () => {
    const disable = vi.fn().mockResolvedValue(undefined);
    vi.mocked(useEnableMfa).mockReturnValue({ mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof useEnableMfa>);
    vi.mocked(useVerifyMfa).mockReturnValue({ mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof useVerifyMfa>);
    vi.mocked(useDisableMfa).mockReturnValue({ mutateAsync: disable, isPending: false } as unknown as ReturnType<typeof useDisableMfa>);

    render(<MfaSection mfaEnabled />);
    fireEvent.click(screen.getByRole("button", { name: "Disable MFA" }));
    fireEvent.change(screen.getByLabelText("Enter a current code to disable MFA"), { target: { value: "654321" } });
    fireEvent.click(screen.getByRole("button", { name: "Disable MFA" }));

    await vi.waitFor(() => expect(disable).toHaveBeenCalledWith("654321"));
  });
});
