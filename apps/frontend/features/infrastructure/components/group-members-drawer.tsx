"use client";

import Link from "next/link";

import { Drawer } from "@/components/overlays/drawer";
import { EmptyState } from "@/components/feedback/empty-state";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useGroupMembers } from "@/features/infrastructure/hooks/use-groups";
import type { AssetGroup } from "@/features/infrastructure/types";

/** `GET /inventory/groups/{id}/members` — live-resolved for dynamic/
 * rule-based groups, stored for every other type (the backend's own
 * distinction). */
export function GroupMembersDrawer({ group, onClose }: { group: AssetGroup | null; onClose: () => void }) {
  const membersQuery = useGroupMembers(group?.id ?? null);

  return (
    <Drawer open={group !== null} onClose={onClose} title={group ? `${group.name} — members` : "Members"}>
      <SectionState isLoading={membersQuery.isLoading} isError={membersQuery.isError} error={membersQuery.error} onRetry={() => membersQuery.refetch()}>
        {membersQuery.data &&
          (membersQuery.data.length === 0 ? (
            <EmptyState title="No members" description="This group currently resolves to no assets." />
          ) : (
            <ul className="flex flex-col gap-2">
              {membersQuery.data.map((asset) => (
                <li key={asset.id}>
                  <Link href={`/infrastructure/assets/${asset.id}`} className="text-sm font-medium hover:underline">
                    {asset.displayName ?? asset.name}
                  </Link>
                  <p className="text-muted-foreground text-xs">{asset.assetType}</p>
                </li>
              ))}
            </ul>
          ))}
      </SectionState>
    </Drawer>
  );
}
