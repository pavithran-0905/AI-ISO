import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LoginForm } from "@/app/(auth)/login/login-form";
import { useAuthStore } from "@/auth/store";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

function mockFetchOnce(status: number, body: unknown, delayMs = 0) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation(
      () =>
        new Promise((resolve) =>
          setTimeout(
            () => resolve({ status, ok: status >= 200 && status < 300, json: () => Promise.resolve(body) }),
            delayMs,
          ),
        ),
    ),
  );
}

function renderForm(returnTo = "/") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <LoginForm returnTo={returnTo} />
    </QueryClientProvider>,
  );
}

async function fillAndSubmit(email: string, password: string) {
  fireEvent.change(screen.getByLabelText(/^Email/), { target: { value: email } });
  fireEvent.change(screen.getByLabelText(/^Password/), { target: { value: password } });
  fireEvent.click(screen.getByRole("button", { name: "Sign In" }));
}

describe("LoginForm", () => {
  afterEach(() => {
    useAuthStore.getState().clear();
    push.mockClear();
    vi.unstubAllGlobals();
  });

  it("shows validation errors and makes no API call when fields are empty", async () => {
    vi.stubGlobal("fetch", vi.fn());
    renderForm();

    fireEvent.click(screen.getByRole("button", { name: "Sign In" }));

    expect(await screen.findByText("Email is required")).toBeInTheDocument();
    expect(screen.getByText("Password is required")).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("rejects a malformed email before calling the API", async () => {
    vi.stubGlobal("fetch", vi.fn());
    renderForm();

    await fillAndSubmit("not-an-email", "hunter2");

    expect(await screen.findByText("Enter a valid email address")).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("logs in successfully and redirects to the given returnTo destination", async () => {
    mockFetchOnce(200, {
      success: true,
      message: "ok",
      data: {
        access_token:
          "header.eyJzdWIiOiJ1MSIsImlzcyI6ImFpLWlvcyIsImlhdCI6MCwiZXhwIjo5OTk5OTk5OTk5LCJqdGkiOiJqMSJ9.sig",
        refresh_token: "refresh-token",
        token_type: "bearer",
        expires_in: 900,
      },
      meta: {},
    });
    renderForm("/monitoring");

    await fillAndSubmit("sarun@example.com", "hunter2");

    await waitFor(() => expect(push).toHaveBeenCalledWith("/monitoring"));
    expect(useAuthStore.getState().status).toBe("authenticated");
  });

  it("shows a safe error and preserves the entered values on invalid credentials", async () => {
    mockFetchOnce(401, {
      success: false,
      message: "Invalid credentials",
      error: { code: "AIIOS-AUTH-0001", details: [] },
      meta: {},
    });
    renderForm();

    await fillAndSubmit("sarun@example.com", "wrong-password");

    expect(await screen.findByText("Unable to sign in with those credentials.")).toBeInTheDocument();
    expect(screen.getByLabelText(/^Email/)).toHaveValue("sarun@example.com");
    expect(screen.getByLabelText(/^Password/)).toHaveValue("wrong-password");
    expect(push).not.toHaveBeenCalled();
  });

  it("shows the exact §19 network-failure message when the API is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    renderForm();

    await fillAndSubmit("sarun@example.com", "hunter2");

    expect(
      await screen.findByText("Unable to connect to the authentication service. Please try again."),
    ).toBeInTheDocument();
  });

  it("shows a generic message on a server error", async () => {
    mockFetchOnce(500, {
      success: false,
      message: "internal error",
      error: { code: "AIIOS-INTERNAL-0001", details: [] },
      meta: {},
    });
    renderForm();

    await fillAndSubmit("sarun@example.com", "hunter2");

    expect(await screen.findByText("Something went wrong on our end. Please try again.")).toBeInTheDocument();
  });

  it("shows a loading state and disables the button while the request is in flight, preventing duplicate submission", async () => {
    mockFetchOnce(
      200,
      {
        success: true,
        message: "ok",
        data: {
          access_token:
            "header.eyJzdWIiOiJ1MSIsImlzcyI6ImFpLWlvcyIsImlhdCI6MCwiZXhwIjo5OTk5OTk5OTk5LCJqdGkiOiJqMSJ9.sig",
          refresh_token: "refresh-token",
          token_type: "bearer",
          expires_in: 900,
        },
        meta: {},
      },
      50,
    );
    renderForm();

    fireEvent.change(screen.getByLabelText(/^Email/), { target: { value: "sarun@example.com" } });
    fireEvent.change(screen.getByLabelText(/^Password/), { target: { value: "hunter2" } });
    const button = screen.getByRole("button", { name: "Sign In" });
    fireEvent.click(button);

    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");

    fireEvent.click(button);
    await waitFor(() => expect(push).toHaveBeenCalled());
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("toggles password visibility with an accessible, keyboard-usable control that never submits the form", () => {
    vi.stubGlobal("fetch", vi.fn());
    renderForm();

    const passwordInput = screen.getByLabelText(/^Password/);
    expect(passwordInput).toHaveAttribute("type", "password");

    const toggle = screen.getByRole("button", { name: "Show password" });
    expect(toggle).toHaveAttribute("type", "button");

    fireEvent.click(toggle);
    expect(passwordInput).toHaveAttribute("type", "text");
    expect(screen.getByRole("button", { name: "Hide password" })).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Hide password" }));
    expect(passwordInput).toHaveAttribute("type", "password");
  });

  it("gives every field a real, non-placeholder-only accessible label", () => {
    vi.stubGlobal("fetch", vi.fn());
    renderForm();

    expect(screen.getByLabelText(/^Email/)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Password/)).toBeInTheDocument();
    expect(screen.getByLabelText("Keep me signed in")).toBeInTheDocument();
  });
});
