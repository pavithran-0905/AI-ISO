"use client";

import Link from "next/link";

import { StatusBadge } from "@/components/feedback/status-badge";
import { buttonVariants } from "@/components/ui/button";
import { ResourceSection } from "@/components/resource/resource-section";
import { AskAiButton } from "@/features/ai-assistant/components/ask-ai-button";
import { AlertActions } from "@/features/alerting/components/alert-actions";
import { AlertCorrelationsList } from "@/features/alerting/components/alert-correlations-list";
import { AlertLifecycleTimeline } from "@/features/alerting/components/alert-lifecycle-timeline";
import { SEVERITY_TONE } from "@/features/alerting/lib/severity";
import type { Alert } from "@/features/alerting/types";

/**
 * §12/§16's Resource/Alert Impact context, for a selected alert.
 * Reuses `AlertActions`/`AlertCorrelationsList`/`AlertLifecycleTimeline`
 * unchanged (Prompt 007) — never a second alert model or a duplicated
 * acknowledge/resolve/escalate flow.
 *
 * No "Open Resource" link exists here: `Alert.sourceReference` is
 * unstructured JSON with no schema-enforced asset id (confirmed by
 * reading `alert_instance.py`'s own model docstring) — the same class
 * of speculative linkage this session refused to build for Audit and
 * Notifications. Shown as opaque, labeled context instead of a
 * fabricated link.
 */
export function AlertContextPanel({ alert }: { alert: Alert }) {
  const hasSourceReference = Object.keys(alert.sourceReference).length > 0;

  return (
    <div className="flex flex-col gap-4">
      <ResourceSection title="Alert">
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge tone={SEVERITY_TONE[alert.severity]} label={alert.severity} className="uppercase" />
            <StatusBadge tone="neutral" label={alert.status} />
          </div>
          <p className="text-sm font-medium">{alert.title}</p>
          <p className="text-muted-foreground text-sm">{alert.message}</p>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
            <div>
              <dt className="text-muted-foreground">Source</dt>
              <dd>{alert.source}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Triggered</dt>
              <dd>{new Date(alert.triggeredAt).toLocaleString()}</dd>
            </div>
          </dl>
          {hasSourceReference && (
            <p className="text-muted-foreground text-xs">
              This alert carries source-identity data, but no guaranteed link to a specific AI-IOS resource — see the
              full alert for its raw context.
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            <Link href={`/alerting/alerts/${alert.id}`} className={buttonVariants("outline")}>
              Open Alert
            </Link>
            <AskAiButton draft={`Investigate this alert: "${alert.title}" (${alert.severity}, ${alert.status}), triggered ${alert.triggeredAt} from ${alert.source}.`} />
          </div>
        </div>
      </ResourceSection>

      <ResourceSection title="Actions">
        <AlertActions alert={alert} />
      </ResourceSection>

      <ResourceSection title="Related alerts">
        <AlertCorrelationsList alertId={alert.id} />
      </ResourceSection>

      <ResourceSection title="History">
        <AlertLifecycleTimeline alertId={alert.id} />
      </ResourceSection>
    </div>
  );
}
