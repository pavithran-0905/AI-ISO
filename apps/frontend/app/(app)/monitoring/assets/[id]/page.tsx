import { MonitoringAssetDetailPage } from "@/features/monitoring/pages/monitoring-asset-detail-page";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <MonitoringAssetDetailPage assetId={id} />;
}
