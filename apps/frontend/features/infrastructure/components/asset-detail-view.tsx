"use client";

import { Copy, Share2 } from "lucide-react";
import Link from "next/link";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/data-display/card";
import { StatusBadge } from "@/components/feedback/status-badge";
import { StatusIndicator } from "@/components/data-display/status-indicator";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { IconButton } from "@/components/ui/icon-button";
import { AskAiButton } from "@/features/ai-assistant/components/ask-ai-button";
import { AssetActions } from "@/features/infrastructure/components/asset-actions";
import { AssetRelationshipsSection } from "@/features/infrastructure/components/asset-relationships-section";
import { TopologySection } from "@/features/infrastructure/components/topology-section";
import { ASSET_HEALTH_TO_STATUS, ASSET_STATUS_TONE, CRITICALITY_TONE, LIFECYCLE_STATE_TONE } from "@/features/infrastructure/lib/status-maps";
import { isSensitiveMetadataKey, maskMetadataValue } from "@/features/infrastructure/lib/sensitive-metadata";
import type { Asset } from "@/features/infrastructure/types";
import { toast } from "@/state/toast-store";

/**
 * Asset Detail (§9) — Identity → Current State/Health → Metadata →
 * Relationships → Topology → Related Operations, per the prompt's own
 * hierarchy. No Events or Metrics section: `GET /observability/events`
 * has no asset-id reference field, and there's no metric-series-
 * discovery endpoint (confirmed absent — see
 * `docs/frontend/backend-v1-integration-limitations.md`), both
 * pre-existing documented gaps, not omissions. No Monitoring or
 * Alerting or Automation cross-link: confirmed absent, no real
 * relationship exists in `inventory-service` to either service (see
 * the developer guide) — only "Ask AI" and "View in Topology" (Prompt
 * 012, §35) are real.
 */
export function AssetDetailView({ asset }: { asset: Asset }) {
  function copyId() {
    void navigator.clipboard.writeText(asset.id);
    toast.info("Asset ID copied");
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex justify-end gap-2">
        <Link href={`/infrastructure/topology?focus=${asset.id}`} className={buttonVariants("outline", "gap-1.5")}>
          <Share2 className="size-4" aria-hidden="true" />
          View in Topology
        </Link>
        <AskAiButton draft={`Tell me about the asset "${asset.name}" (id: ${asset.id}).`} />
      </div>

      <IdentitySection asset={asset} onCopyId={copyId} />

      <Card>
        <CardHeader>
          <CardTitle>Actions</CardTitle>
        </CardHeader>
        <CardContent>
          <AssetActions asset={asset} />
        </CardContent>
      </Card>

      <StateSection asset={asset} />
      <MetadataSection asset={asset} />
      <AssetRelationshipsSection asset={asset} />
      <TopologySection assetId={asset.id} />
    </div>
  );
}

function IdentitySection({ asset, onCopyId }: { asset: Asset; onCopyId: () => void }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Identity</CardTitle>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
          <Field label="Name" value={asset.name} />
          <Field label="Display name" value={asset.displayName} />
          <Field label="Type" value={asset.assetType} />
          <Field label="Hostname" value={asset.hostname} />
          <Field label="FQDN" value={asset.fqdn} />
          <Field label="IP address" value={asset.ipAddress} />
          <Field label="MAC address" value={asset.macAddress} mono />
          <Field label="Serial number" value={asset.serialNumber} mono />
          <Field label="Vendor" value={asset.vendor} />
          <Field label="Manufacturer" value={asset.manufacturer} />
          <Field label="Model" value={asset.model} />
          <Field label="Firmware version" value={asset.firmwareVersion} />
          <Field label="Operating system" value={asset.operatingSystem} />
          <Field label="Architecture" value={asset.architecture} />
          <Field label="Environment" value={asset.environment} />
          <div className="flex flex-col gap-0.5">
            <dt className="text-muted-foreground text-xs">Asset ID</dt>
            <dd className="flex items-center gap-1 font-mono text-xs">
              {asset.id}
              <IconButton icon={Copy} aria-label="Copy asset ID" variant="ghost" onClick={onCopyId} className="size-5" />
            </dd>
          </div>
        </dl>
      </CardContent>
    </Card>
  );
}

function StateSection({ asset }: { asset: Asset }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Current state</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-wrap items-center gap-6">
        <div className="flex flex-col gap-1">
          <p className="text-muted-foreground text-xs">Health</p>
          <StatusIndicator state={ASSET_HEALTH_TO_STATUS[asset.health]} />
        </div>
        <div className="flex flex-col gap-1">
          <p className="text-muted-foreground text-xs">Status</p>
          <StatusBadge tone={ASSET_STATUS_TONE[asset.status]} label={asset.status} />
        </div>
        <div className="flex flex-col gap-1">
          <p className="text-muted-foreground text-xs">Lifecycle</p>
          <StatusBadge tone={LIFECYCLE_STATE_TONE[asset.lifecycleState]} label={asset.lifecycleState} />
        </div>
        <div className="flex flex-col gap-1">
          <p className="text-muted-foreground text-xs">Criticality</p>
          <StatusBadge tone={CRITICALITY_TONE[asset.criticality]} label={asset.criticality} />
        </div>
        <div className="flex flex-col gap-1">
          <p className="text-muted-foreground text-xs">Version</p>
          <p className="text-sm font-medium tabular-nums">{asset.currentVersion}</p>
        </div>
        <div className="flex flex-col gap-1">
          <p className="text-muted-foreground text-xs">Last updated</p>
          <p className="text-sm font-medium">
            <time dateTime={asset.updatedAt}>{new Date(asset.updatedAt).toLocaleString()}</time>
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

function MetadataSection({ asset }: { asset: Asset }) {
  const metadataEntries = Object.entries(asset.metadata);
  // category_id/class_id/location_id/owner_id have no name-resolution
  // endpoint on inventory-service (confirmed by source inspection) —
  // shown as raw identifiers, clearly labeled as ids, rather than
  // invented names.
  return (
    <Card>
      <CardHeader>
        <CardTitle>Metadata</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {asset.tags.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {asset.tags.map((tag) => (
              <Badge key={tag} variant="outline">
                {tag}
              </Badge>
            ))}
          </div>
        )}
        <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
          <Field label="Category id" value={asset.categoryId} mono />
          <Field label="Class id" value={asset.classId} mono />
          <Field label="Location id" value={asset.locationId} mono />
          <Field label="Owner id" value={asset.ownerId} mono />
          <Field label="Project id" value={asset.projectId} mono />
        </dl>
        {metadataEntries.length > 0 && (
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
            {metadataEntries.map(([key, value]) => (
              <Field
                key={key}
                label={key}
                value={maskMetadataValue(key, value)}
                mono={isSensitiveMetadataKey(key)}
              />
            ))}
          </dl>
        )}
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
