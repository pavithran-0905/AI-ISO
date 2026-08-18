import { TemplateDetailPage } from "@/features/reporting/pages/template-detail-page";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <TemplateDetailPage templateId={id} />;
}
