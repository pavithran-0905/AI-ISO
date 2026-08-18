import { ExecutionDetailPage } from "@/features/automation/pages/execution-detail-page";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ExecutionDetailPage executionId={id} />;
}
