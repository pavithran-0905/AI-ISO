"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/data-display/card";
import { StatusBadge } from "@/components/feedback/status-badge";
import { AlertAcknowledgementsList } from "@/features/alerting/components/alert-acknowledgements-list";
import { AlertActions } from "@/features/alerting/components/alert-actions";
import { AlertCorrelationsList } from "@/features/alerting/components/alert-correlations-list";
import { AlertLifecycleTimeline } from "@/features/alerting/components/alert-lifecycle-timeline";
import { AlertNotificationsList } from "@/features/alerting/components/alert-notifications-list";
import { SEVERITY_LABEL, SEVERITY_TONE } from "@/features/alerting/lib/severity";
import type { Alert } from "@/features/alerting/types";

/**
 * Alert Detail (§9's 12-point hierarchy) — Identity → Severity/Status →
 * Source → Timestamps → Description → Lifecycle → Acknowledgements →
 * Correlations → Notifications → Actions. No separate "Metadata"
 * section: unlike `Asset`, `AlertResponse` carries no arbitrary
 * key/value metadata field (confirmed by source inspection) — nothing
 * was omitted, there's simply nothing there.
 */
export function AlertDetailView({ alert }: { alert: Alert }) {
  return (
    <div className="flex flex-col gap-6">
      <IdentitySection alert={alert} />
      <SeverityStatusSection alert={alert} />
      <TimestampsSection alert={alert} />
      <DescriptionSection alert={alert} />

      <Card>
        <CardHeader>
          <CardTitle>Actions</CardTitle>
        </CardHeader>
        <CardContent>
          <AlertActions alert={alert} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Lifecycle</CardTitle>
        </CardHeader>
        <CardContent>
          <AlertLifecycleTimeline alertId={alert.id} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Acknowledgements</CardTitle>
        </CardHeader>
        <CardContent>
          <AlertAcknowledgementsList alertId={alert.id} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Correlated alerts</CardTitle>
        </CardHeader>
        <CardContent>
          <AlertCorrelationsList alertId={alert.id} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Notifications</CardTitle>
        </CardHeader>
        <CardContent>
          <AlertNotificationsList alertId={alert.id} />
        </CardContent>
      </Card>
    </div>
  );
}

function IdentitySection({ alert }: { alert: Alert }) {
  const sourceReferenceEntries = Object.entries(alert.sourceReference);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Identity</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
          <Field label="Alert id" value={alert.id} mono />
          <Field label="Organization id" value={alert.organizationId} mono />
          <Field label="Project id" value={alert.projectId} mono />
          <Field label="Rule id" value={alert.ruleId} mono />
          <Field label="Fingerprint" value={alert.fingerprint} mono />
          <Field label="Assigned to" value={alert.assignedTo} mono />
        </dl>
        {sourceReferenceEntries.length > 0 && (
          <div>
            {/* Free-form, caller-supplied at ingestion — no fixed
             * schema, so shown as raw key/value pairs rather than a
             * single field (see `Alert.sourceReference`'s own
             * docstring). */}
            <p className="text-muted-foreground mb-2 text-xs">Source reference</p>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
              {sourceReferenceEntries.map(([key, value]) => (
                <Field key={key} label={key} value={String(value)} mono />
              ))}
            </dl>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function SeverityStatusSection({ alert }: { alert: Alert }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Severity &amp; status</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-wrap items-center gap-6">
        <div className="flex flex-col gap-1">
          <p className="text-muted-foreground text-xs">Severity</p>
          <StatusBadge tone={SEVERITY_TONE[alert.severity]} label={SEVERITY_LABEL[alert.severity]} />
        </div>
        <div className="flex flex-col gap-1">
          <p className="text-muted-foreground text-xs">Status</p>
          <p className="text-sm font-medium">{alert.status}</p>
        </div>
        <div className="flex flex-col gap-1">
          <p className="text-muted-foreground text-xs">Source</p>
          <p className="text-sm font-medium">{alert.source}</p>
        </div>
      </CardContent>
    </Card>
  );
}

function TimestampsSection({ alert }: { alert: Alert }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Timestamps</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-wrap gap-6">
        <TimeField label="Triggered" value={alert.triggeredAt} />
        <TimeField label="Resolved" value={alert.resolvedAt} />
        <TimeField label="Closed" value={alert.closedAt} />
      </CardContent>
    </Card>
  );
}

function DescriptionSection({ alert }: { alert: Alert }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Description</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        <p className="text-sm font-medium">{alert.title}</p>
        {alert.message ? <p className="text-muted-foreground text-sm">{alert.message}</p> : <p className="text-muted-foreground text-sm">No message.</p>}
      </CardContent>
    </Card>
  );
}

function Field({ label, value, mono = false }: { label: string; value: string | null; mono?: boolean }) {
  if (!value) return null;
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-muted-foreground text-xs">{label}</dt>
      <dd className={mono ? "font-mono text-xs" : "text-sm"}>{value}</dd>
    </div>
  );
}

function TimeField({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="flex flex-col gap-1">
      <p className="text-muted-foreground text-xs">{label}</p>
      <p className="text-sm font-medium">{value ? <time dateTime={value}>{new Date(value).toLocaleString()}</time> : "—"}</p>
    </div>
  );
}
