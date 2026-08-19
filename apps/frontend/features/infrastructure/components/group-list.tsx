"use client";

import { Users2 } from "lucide-react";

import { Card, CardContent } from "@/components/data-display/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/feedback/empty-state";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useGroups } from "@/features/infrastructure/hooks/use-groups";
import type { AssetGroup } from "@/features/infrastructure/types";

export function GroupList({ organizationId, onSelect }: { organizationId: string; onSelect: (group: AssetGroup) => void }) {
  const groupsQuery = useGroups(organizationId);

  return (
    <SectionState isLoading={groupsQuery.isLoading} isError={groupsQuery.isError} error={groupsQuery.error} onRetry={() => groupsQuery.refetch()}>
      {groupsQuery.data &&
        (groupsQuery.data.length === 0 ? (
          <EmptyState icon={Users2} title="No groups yet" description="Create one below." />
        ) : (
          <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {groupsQuery.data.map((group) => (
              <li key={group.id}>
                <button type="button" onClick={() => onSelect(group)} className="block w-full text-left">
                  <Card className="hover:border-muted-foreground/50 transition-colors">
                    <CardContent className="flex flex-col gap-2 p-4">
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-sm font-medium">{group.name}</p>
                        <Badge variant="outline">{group.groupType}</Badge>
                      </div>
                      {group.description && <p className="text-muted-foreground text-xs">{group.description}</p>}
                      <p className="text-muted-foreground text-xs">
                        {group.memberAssetIds.length} member{group.memberAssetIds.length === 1 ? "" : "s"}
                      </p>
                    </CardContent>
                  </Card>
                </button>
              </li>
            ))}
          </ul>
        ))}
    </SectionState>
  );
}
