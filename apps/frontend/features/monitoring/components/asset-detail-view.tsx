"use client";

import Link from "next/link";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/data-display/card";
import { StatusIndicator } from "@/components/data-display/status-indicator";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/feedback/empty-state";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useAssetRelationships } from "@/features/monitoring/hooks/use-asset-relationships";
import { ASSET_HEALTH_TO_STATUS } from "@/features/monitoring/lib/status-maps";
import type { Asset } from "@/features/monitoring/types";

/**
 * Asset Detail (§8) — Identity → Current Health → Metadata → Related
 * Assets, in that order (the prompt's own hierarchy). No Events or
 * Metrics section: `GET /observability/events` has no asset-id
 * reference field, and there's no metric-series-discovery endpoint —
 * both are documented limitations
 * (`docs/frontend/backend-v1-integration-limitations.md`), not
 * omissions.
 */
export function AssetDetailView({ asset }: { asset: Asset }) {
  return (
    <div className="flex flex-col gap-6">
      <IdentitySection asset={asset} />
      <HealthSection asset={asset} />
      <MetadataSection asset={asset} />
      <RelatedAssetsSection assetId={asset.id} />
    </div>
  );
}

function IdentitySection({ asset }: { asset: Asset }) {
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
          <Field label="Vendor" value={asset.vendor} />
          <Field label="Model" value={asset.model} />
          <Field label="Operating system" value={asset.operatingSystem} />
          <Field label="Environment" value={asset.environment} />
        </dl>
      </CardContent>
    </Card>
  );
}

function HealthSection({ asset }: { asset: Asset }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Current health</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-wrap items-center gap-6">
        <div className="flex flex-col gap-1">
          <p className="text-muted-foreground text-xs">Health</p>
          <StatusIndicator state={ASSET_HEALTH_TO_STATUS[asset.health]} />
        </div>
        <div className="flex flex-col gap-1">
          <p className="text-muted-foreground text-xs">Status</p>
          <p className="text-sm font-medium">{asset.status}</p>
        </div>
        <div className="flex flex-col gap-1">
          <p className="text-muted-foreground text-xs">Lifecycle</p>
          <p className="text-sm font-medium">{asset.lifecycleState}</p>
        </div>
        <div className="flex flex-col gap-1">
          <p className="text-muted-foreground text-xs">Criticality</p>
          <p className="text-sm font-medium">{asset.criticality}</p>
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
        </dl>
        {metadataEntries.length > 0 && (
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
            {metadataEntries.map(([key, value]) => (
              <Field key={key} label={key} value={String(value)} />
            ))}
          </dl>
        )}
      </CardContent>
    </Card>
  );
}

function RelatedAssetsSection({ assetId }: { assetId: string }) {
  const query = useAssetRelationships(assetId);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Related assets</CardTitle>
      </CardHeader>
      <CardContent>
        <SectionState isLoading={query.isLoading} isError={query.isError} error={query.error} onRetry={() => query.refetch()}>
          {query.data &&
            (query.data.length === 0 ? (
              <EmptyState title="No related assets" description="No relationships have been recorded for this asset." />
            ) : (
              <ul className="flex flex-col gap-2">
                {query.data.map((relationship) => (
                  <li key={relationship.id} className="flex items-center justify-between gap-3 text-sm">
                    <span className="text-muted-foreground">{relationship.relationshipType}</span>
                    <Link
                      href={`/monitoring/assets/${relationship.targetAssetId}`}
                      className="font-mono text-xs hover:underline"
                    >
                      {relationship.targetAssetId}
                    </Link>
                  </li>
                ))}
              </ul>
            ))}
        </SectionState>
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
