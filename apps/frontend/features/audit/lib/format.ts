/** Every action value across all three sources is `snake_case` — this
 * only reformats for display, it never invents a value the backend
 * didn't send. */
export function formatActionLabel(action: string): string {
  return action
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

/** `succeeded: boolean` is the only status field any of the three
 * sources returns — no "denied"/"pending"/other status exists on this
 * backend, so only these two are ever shown (§12 forbids inventing a
 * frontend-only status model). */
export function eventStatusLabel(succeeded: boolean): "Success" | "Failure" {
  return succeeded ? "Success" : "Failure";
}
