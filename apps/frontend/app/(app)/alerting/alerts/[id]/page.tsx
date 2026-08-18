import { AlertingAlertDetailPage } from "@/features/alerting/pages/alerting-alert-detail-page";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <AlertingAlertDetailPage alertId={id} />;
}
