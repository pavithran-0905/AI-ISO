import { describe, expect, it } from "vitest";

import { alertToResult, assetToResult, automationToResult, conversationToResult, reportToResult, userToResult } from "@/features/search/lib/adapters";
import type { Alert } from "@/features/alerting/types";
import type { AutomationJob } from "@/features/automation/types";
import type { Conversation } from "@/features/ai-assistant/types";
import type { Asset } from "@/features/infrastructure/types";
import type { Report } from "@/features/reporting/types";
import type { UserSummary } from "@/features/administration/types";

describe("search adapters", () => {
  it("maps a real Asset to a normalized result with a real detail route", () => {
    const asset = { id: "a1", displayName: "edge-01", name: "edge-01-raw", hostname: "edge-01.internal", assetType: "physical_server", status: "managed" } as Asset;
    expect(assetToResult(asset)).toMatchObject({ id: "a1", resultType: "asset", title: "edge-01", description: "edge-01.internal", status: "Managed", href: "/infrastructure/assets/a1" });
  });

  it("falls back to the raw name when an asset has no display name", () => {
    const asset = { id: "a1", displayName: null, name: "edge-01-raw", hostname: null, assetType: "virtual_machine", status: "managed" } as Asset;
    expect(assetToResult(asset).title).toBe("edge-01-raw");
    expect(assetToResult(asset).description).toBe("Virtual Machine");
  });

  it("maps a real UserSummary to a normalized result", () => {
    const user = { id: "u1", username: "sarun", email: "sarun@example.com", displayName: "Sarun M", status: "active" } as UserSummary;
    expect(userToResult(user)).toMatchObject({ id: "u1", resultType: "user", title: "Sarun M", description: "sarun@example.com", status: "Active", href: "/administration/users/u1" });
  });

  it("truncates a long alert message rather than dumping it whole into the result preview", () => {
    const longMessage = "x".repeat(100);
    const alert = { id: "al1", title: "CPU threshold exceeded", message: longMessage, status: "open" } as Alert;
    const result = alertToResult(alert);
    expect(result.description?.length).toBeLessThan(longMessage.length);
    expect(result.description?.endsWith("…")).toBe(true);
    expect(result.href).toBe("/alerting/alerts/al1");
  });

  it("maps a real AutomationJob to a normalized result", () => {
    const job = { id: "j1", name: "Deploy service", description: "Deploys the app", automationType: "playbook", status: "active" } as unknown as AutomationJob;
    expect(automationToResult(job)).toMatchObject({ id: "j1", resultType: "automation", title: "Deploy service", description: "Deploys the app", href: "/automation/automations/j1" });
  });

  it("maps a real Report to a normalized result, showing enabled/disabled since no status field exists", () => {
    const report = { id: "r1", name: "Weekly infra summary", description: null, category: "infrastructure", enabled: true } as Report;
    expect(reportToResult(report)).toMatchObject({ id: "r1", resultType: "report", title: "Weekly infra summary", description: "Infrastructure", status: "Enabled", href: "/reporting/reports/r1" });
  });

  it("deep-links a conversation to the real, already-established ?conversation= param, never a fabricated route", () => {
    const conversation = { id: "c1", title: "Why is edge-01 unhealthy?", status: "active" } as Conversation;
    expect(conversationToResult(conversation)).toMatchObject({ id: "c1", resultType: "conversation", title: "Why is edge-01 unhealthy?", href: "/intelligence/assistant?conversation=c1" });
  });
});
