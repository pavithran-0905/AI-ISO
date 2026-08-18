import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useAcknowledgeAlert } from "@/features/alerting/hooks/use-acknowledge-alert";
import { useCloseAlert } from "@/features/alerting/hooks/use-close-alert";
import { useEscalateAlert } from "@/features/alerting/hooks/use-escalate-alert";
import { useResolveAlert } from "@/features/alerting/hooks/use-resolve-alert";

function ALERT_BODY() {
  return {
    id: "a1",
    organization_id: "org-1",
    project_id: null,
    rule_id: null,
    source: "monitoring",
    severity: "high",
    status: "acknowledged",
    title: "Database unreachable",
    message: "Connection refused",
    fingerprint: "fp-1",
    source_reference: {},
    assigned_to: null,
    triggered_at: "2026-01-01T00:00:00Z",
    resolved_at: null,
    closed_at: null,
  };
}

function envelope(data: unknown) {
  return { success: true, message: "ok", data, meta: {} };
}

function errorEnvelope() {
  return { success: false, message: "Invalid transition", error: { code: "AIIOS-ALERT-0001", details: [] }, meta: {} };
}

function wrapper({ children }: { children: React.ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

function mockFetchOnce(status: number, body: unknown) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ status, ok: status >= 200 && status < 300, json: () => Promise.resolve(body) }));
}

describe("alert mutation hooks", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("useAcknowledgeAlert waits for the real backend response before succeeding", async () => {
    mockFetchOnce(200, envelope(ALERT_BODY()));
    const { result } = renderHook(() => useAcknowledgeAlert("a1"), { wrapper });

    result.current.mutate("on it");

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/alerts/a1/acknowledge"),
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("useAcknowledgeAlert surfaces a rejected mutation without pretending success", async () => {
    mockFetchOnce(409, errorEnvelope());
    const { result } = renderHook(() => useAcknowledgeAlert("a1"), { wrapper });

    result.current.mutate(undefined);

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.isSuccess).toBe(false);
  });

  it("useResolveAlert posts resolution notes and waits for confirmation", async () => {
    mockFetchOnce(200, envelope({ ...ALERT_BODY(), status: "resolved" }));
    const { result } = renderHook(() => useResolveAlert("a1"), { wrapper });

    result.current.mutate("fixed the replica");

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/alerts/a1/resolve"),
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("useEscalateAlert surfaces failure without an optimistic update", async () => {
    mockFetchOnce(400, errorEnvelope());
    const { result } = renderHook(() => useEscalateAlert("a1"), { wrapper });

    result.current.mutate({ reason: "needs on-call" });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });

  it("useCloseAlert calls the real status-transition DELETE route", async () => {
    mockFetchOnce(200, envelope({ ...ALERT_BODY(), status: "closed" }));
    const { result } = renderHook(() => useCloseAlert("a1"), { wrapper });

    result.current.mutate();

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(fetch).toHaveBeenCalledWith(expect.stringContaining("/alerts/a1"), expect.objectContaining({ method: "DELETE" }));
  });
});
