import { Switch } from "@/components/forms/switch";

/**
 * The honest implementation of §19's "action confirmation" requirement.
 * The real backend contract has no interactive per-tool-call
 * confirmation round-trip — a mutating tool is either allowed for the
 * whole turn or denied outright within it (see `SendMessageInput`'s
 * own docstring). So this is a composer-level, OFF-by-default,
 * pre-emptive consent sent WITH the request, never a fake mid-turn
 * "the assistant wants to do X, allow?" dialog.
 */
export function MutatingToolsToggle({ checked, onChange }: { checked: boolean; onChange: (checked: boolean) => void }) {
  return (
    <label className="flex items-start gap-2 text-xs">
      <Switch checked={checked} onChange={(event) => onChange(event.target.checked)} aria-label="Allow this assistant to take actions that change infrastructure" className="mt-0.5" />
      <span className="text-muted-foreground">
        Allow this assistant to take actions that change infrastructure for this message. Off by default.
      </span>
    </label>
  );
}
