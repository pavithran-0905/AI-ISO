"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";

import { PageHeader } from "@/components/navigation/page-header";
import { buttonVariants } from "@/components/ui/button";
import { NotificationDetailView } from "@/features/notifications/components/notification-detail-view";
import { useNotification } from "@/features/notifications/hooks/use-notifications";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useSelectedOrganization } from "@/organization/use-organizations";

/** Notification Detail — `/notifications/[id]` (§8). Unlike Prompt
 * 015's Audit Event Detail, this is a real route backed by a real
 * `GET /notifications/{id}` — no service-level limitation forces a
 * drawer here. */
export function NotificationDetailPage({ notificationId }: { notificationId: string }) {
  const { selectedOrganizationId } = useSelectedOrganization();
  const query = useNotification(selectedOrganizationId, notificationId);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={query.data?.subject ?? "Notification"}
        description={query.data ? undefined : "Loading…"}
        secondaryActions={
          <Link href="/notifications" className={buttonVariants("outline", "gap-1.5")}>
            <ArrowLeft className="size-4" aria-hidden="true" />
            Back to Notifications
          </Link>
        }
      />
      <SectionState isLoading={query.isLoading} isError={query.isError} error={query.error} onRetry={() => query.refetch()} skeletonClassName="h-96 w-full">
        {query.data && selectedOrganizationId && <NotificationDetailView organizationId={selectedOrganizationId} notification={query.data} />}
      </SectionState>
    </div>
  );
}
