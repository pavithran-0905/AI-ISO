/**
 * There is no incident entity, database, or lifecycle anywhere in
 * AI-IOS's backend (confirmed absent — no service exposes an
 * `/incidents` route or model). Per this prompt's own explicit
 * instruction, this feature is named and modeled as an **Operations
 * Workspace** — a frontend-only correlation view over existing,
 * already-built feature data — never presented as if a backend
 * incident-management system exists. See
 * `docs/frontend/developer-guide/operations-workspace.md` for the
 * full reasoning, and `docs/frontend/backend-v1-integration-limitations.md`
 * for exactly which correlations are real versus confirmed absent.
 */

/** The only two real, independently-fetched "signal" sources this
 * workspace shows — an `Alert` (`@/features/alerting/types`) or an
 * `AutomationExecution` (`@/features/automation/types`), reused
 * unchanged from their own owning features (§16/§41: "use existing
 * Alerting components... do not create another alert model"). Never
 * merged into one combined list — each keeps its own real identity,
 * ordering, and fields. */
export type OperationalSignalRef = { kind: "alert"; id: string } | { kind: "execution"; id: string };

export function signalRefToParam(ref: OperationalSignalRef): string {
  return `${ref.kind}:${ref.id}`;
}

export function parseSignalParam(value: string | null): OperationalSignalRef | null {
  if (!value) return null;
  const [kind, id] = value.split(":");
  if (!id) return null;
  if (kind === "alert" || kind === "execution") return { kind, id };
  return null;
}
