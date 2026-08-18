import { AutomationEditPage } from "@/features/automation/pages/automation-edit-page";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <AutomationEditPage jobId={id} />;
}
