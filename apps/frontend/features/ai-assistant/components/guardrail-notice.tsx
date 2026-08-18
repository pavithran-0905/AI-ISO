import { Alert } from "@/components/feedback/alert";

/**
 * `ChatResult.guardrailFindings` holds raw internal pattern-category
 * strings (e.g. `"instruction_override"`, `"private_key"`) — those are
 * guardrail-rule implementation details, never rendered verbatim (§20:
 * distinguish a guardrail rejection from a system error, without
 * leaking how the guardrail works). A non-empty array only ever shows
 * this one calm, generic notice.
 */
export function GuardrailNotice({ findingsCount }: { findingsCount: number }) {
  if (findingsCount === 0) return null;

  return (
    <Alert tone="warning" title="Part of this response was filtered for safety">
      The assistant withheld content that didn&apos;t pass a safety check. Try rephrasing your request.
    </Alert>
  );
}
