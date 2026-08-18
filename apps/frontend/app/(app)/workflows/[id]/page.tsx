import { WorkflowDetailPage } from "@/features/workflows/pages/workflow-detail-page";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <WorkflowDetailPage workflowId={id} />;
}
