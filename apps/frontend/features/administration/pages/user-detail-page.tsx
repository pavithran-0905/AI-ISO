"use client";

import { useRouter } from "next/navigation";

import { PageHeader } from "@/components/navigation/page-header";
import { Button } from "@/components/ui/button";
import { SectionState } from "@/features/dashboard/components/section-state";
import { UserDetailView } from "@/features/administration/components/user-detail-view";
import { useUser } from "@/features/administration/hooks/use-users";

/** User Detail — `/administration/users/[id]`. Not registered in the
 * flat route registry (dynamic id) — own "Back to…" action, same
 * pattern as every other dynamic detail page in this app. */
export function UserDetailPage({ userId }: { userId: string }) {
  const router = useRouter();
  const query = useUser(userId);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={query.data?.displayName ?? query.data?.username ?? "User"}
        description={query.data?.email}
        secondaryActions={
          <Button variant="outline" onClick={() => router.push("/administration/users")}>
            Back to Users
          </Button>
        }
      />
      <SectionState isLoading={query.isLoading} isError={query.isError} error={query.error} onRetry={() => query.refetch()} skeletonClassName="h-96 w-full">
        {query.data && <UserDetailView user={query.data} />}
      </SectionState>
    </div>
  );
}
