import { ReportDetailPage } from "@/features/reporting/pages/report-detail-page";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ReportDetailPage reportId={id} />;
}
