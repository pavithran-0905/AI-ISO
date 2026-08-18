import type { AutomationExecution } from "@/features/automation/types";

/** The backend stores an execution's selected target ids inside its
 * own `variables` dict under this key (`app/services/execution.py`)
 * rather than as a first-class field — so it round-trips back to us
 * mixed in with the operator's real variables. */
const TARGET_IDS_KEY = "_target_ids";

export interface SplitExecutionVariables {
  /** The operator-meaningful variables, with the backend's internal
   * bookkeeping key removed. */
  variables: Record<string, unknown>;
  /** The target ids this execution ran against — the only way to
   * recover them, since `AutomationExecutionResponse` has no `targets`
   * field. Empty when the run had no targets (which means it ran
   * locally on the automation-service container). */
  targetIds: string[];
}

/** Separates the backend's internal `_target_ids` bookkeeping from the
 * operator's own variables, so neither is shown as the other. */
export function splitExecutionVariables(execution: AutomationExecution): SplitExecutionVariables {
  const { [TARGET_IDS_KEY]: rawTargetIds, ...variables } = execution.variables;
  const targetIds = Array.isArray(rawTargetIds) ? rawTargetIds.map(String) : [];
  return { variables, targetIds };
}
