import { AssetDetailPage } from "@/features/infrastructure/pages/asset-detail-page";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <AssetDetailPage assetId={id} />;
}
