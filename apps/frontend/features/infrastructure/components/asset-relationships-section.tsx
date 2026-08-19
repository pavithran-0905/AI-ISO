"use client";

import { Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { ApiRequestError } from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/data-display/card";
import { Button } from "@/components/ui/button";
import { IconButton } from "@/components/ui/icon-button";
import { Dialog } from "@/components/overlays/dialog";
import { Label } from "@/components/forms/label";
import { Select } from "@/components/forms/select";
import { EmptyState } from "@/components/feedback/empty-state";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useAllAssets } from "@/features/infrastructure/hooks/use-assets";
import { useAssetRelationships, useCreateRelationship, useDeleteRelationship } from "@/features/infrastructure/hooks/use-relationships";
import { resolveRelationshipNeighbor } from "@/features/infrastructure/lib/relationship-direction";
import { RELATIONSHIP_TYPES, type Asset, type RelationshipTypeValue } from "@/features/infrastructure/types";
import { usePermissions } from "@/permissions/hooks";
import { toast } from "@/state/toast-store";

/**
 * Relationships (§15) — a real, structured list, never a fabricated
 * topology graph (§53 forbids the dependency; see
 * `TopologySection` for the genuinely available structured neighbor/
 * dependency/impact data). Create and delete are both real routes
 * (`POST`/`DELETE /inventory/relationships`) — a capability
 * `features/monitoring`'s prior read-only view never had.
 */
export function AssetRelationshipsSection({ asset }: { asset: Asset }) {
  const { can } = usePermissions();
  const [addOpen, setAddOpen] = useState(false);
  const relationshipsQuery = useAssetRelationships(asset.id);
  const allAssetsQuery = useAllAssets(asset.organizationId);
  const createRelationship = useCreateRelationship();
  const deleteRelationship = useDeleteRelationship();

  const nameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const other of allAssetsQuery.data ?? []) map.set(other.id, other.displayName ?? other.name);
    return map;
  }, [allAssetsQuery.data]);

  async function handleDelete(relationshipId: string) {
    try {
      await deleteRelationship.mutateAsync(relationshipId);
      toast.success("Relationship removed");
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not remove relationship", message);
    }
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <CardTitle>Relationships</CardTitle>
        {can("update") && (
          <IconButton icon={Plus} aria-label="Add relationship" variant="outline" onClick={() => setAddOpen(true)} />
        )}
      </CardHeader>
      <CardContent>
        <SectionState
          isLoading={relationshipsQuery.isLoading}
          isError={relationshipsQuery.isError}
          error={relationshipsQuery.error}
          onRetry={() => relationshipsQuery.refetch()}
        >
          {relationshipsQuery.data &&
            (relationshipsQuery.data.length === 0 ? (
              <EmptyState title="No relationships available" description="Nothing has been recorded for this asset." />
            ) : (
              <ul className="flex flex-col gap-2">
                {relationshipsQuery.data.map((relationship) => {
                  const { neighborAssetId, direction } = resolveRelationshipNeighbor(relationship, asset.id);
                  return (
                    <li key={relationship.id} className="flex items-center justify-between gap-3 text-sm">
                      <div className="flex items-center gap-2">
                        <span className="text-muted-foreground">
                          {direction === "outgoing" ? relationship.relationshipType : `${relationship.relationshipType} (incoming)`}
                        </span>
                        <Link href={`/infrastructure/assets/${neighborAssetId}`} className="font-medium hover:underline">
                          {nameById.get(neighborAssetId) ?? neighborAssetId}
                        </Link>
                      </div>
                      {can("update") && (
                        <IconButton
                          icon={Trash2}
                          aria-label="Remove relationship"
                          variant="ghost"
                          onClick={() => void handleDelete(relationship.id)}
                          loading={deleteRelationship.isPending}
                        />
                      )}
                    </li>
                  );
                })}
              </ul>
            ))}
        </SectionState>
      </CardContent>

      <AddRelationshipDialog
        asset={asset}
        candidates={(allAssetsQuery.data ?? []).filter((candidate) => candidate.id !== asset.id)}
        open={addOpen}
        onClose={() => setAddOpen(false)}
        onCreate={async (targetAssetId, relationshipType) => {
          try {
            await createRelationship.mutateAsync({
              organizationId: asset.organizationId,
              sourceAssetId: asset.id,
              targetAssetId,
              relationshipType,
            });
            toast.success("Relationship added");
            setAddOpen(false);
          } catch (error) {
            const message = error instanceof ApiRequestError ? error.message : "Please try again.";
            toast.danger("Could not add relationship", message);
          }
        }}
        isPending={createRelationship.isPending}
      />
    </Card>
  );
}

function AddRelationshipDialog({
  asset,
  candidates,
  open,
  onClose,
  onCreate,
  isPending,
}: {
  asset: Asset;
  candidates: Asset[];
  open: boolean;
  onClose: () => void;
  onCreate: (targetAssetId: string, relationshipType: RelationshipTypeValue) => void;
  isPending: boolean;
}) {
  const [targetAssetId, setTargetAssetId] = useState("");
  const [relationshipType, setRelationshipType] = useState<RelationshipTypeValue>("depends_on");

  return (
    <Dialog open={open} onClose={onClose} title={`Add a relationship from ${asset.displayName ?? asset.name}`}>
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="relationship-target">Target asset</Label>
          <Select id="relationship-target" value={targetAssetId} onChange={(event) => setTargetAssetId(event.target.value)}>
            <option value="">Select an asset…</option>
            {candidates.map((candidate) => (
              <option key={candidate.id} value={candidate.id}>
                {candidate.displayName ?? candidate.name}
              </option>
            ))}
          </Select>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="relationship-type">Relationship type</Label>
          <Select
            id="relationship-type"
            value={relationshipType}
            onChange={(event) => setRelationshipType(event.target.value as RelationshipTypeValue)}
          >
            {RELATIONSHIP_TYPES.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </Select>
        </div>
        <Button
          onClick={() => targetAssetId && onCreate(targetAssetId, relationshipType)}
          disabled={!targetAssetId}
          loading={isPending}
          className="w-fit"
        >
          Add relationship
        </Button>
      </div>
    </Dialog>
  );
}
