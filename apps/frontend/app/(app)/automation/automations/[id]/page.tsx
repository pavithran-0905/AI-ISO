import { AutomationDetailPage } from "@/features/automation/pages/automation-detail-page";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <AutomationDetailPage jobId={id} />;
}
