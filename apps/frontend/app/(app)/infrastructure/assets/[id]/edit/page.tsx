import { AssetEditPage } from "@/features/infrastructure/pages/asset-edit-page";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <AssetEditPage assetId={id} />;
}
