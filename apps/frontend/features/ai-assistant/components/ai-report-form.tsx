"use client";

import { useState } from "react";

import { ApiRequestError } from "@/api/client";
import { Input } from "@/components/forms/input";
import { Label } from "@/components/forms/label";
import { Select } from "@/components/forms/select";
import { Button } from "@/components/ui/button";
import { useGenerateAiReport } from "@/features/ai-assistant/hooks/use-insights";
import { AI_REPORT_TYPES, type AiReportTypeValue } from "@/features/ai-assistant/types";
import { toast } from "@/state/toast-store";

/** `AiReportRequest.parameters` is a genuinely free-form `dict[str, Any]`
 * with no defined schema anywhere in the backend — there is nothing to
 * build a structured editor against, so this form omits one and always
 * sends `{}`, rather than inventing a shape the backend never
 * documents. */
export function AiReportForm({ organizationId }: { organizationId: string }) {
  const [reportType, setReportType] = useState<AiReportTypeValue>("operational");
  const [subject, setSubject] = useState("");
  const [error, setError] = useState<string | null>(null);
  const generateReport = useGenerateAiReport();

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!subject.trim()) {
      setError("Subject is required.");
      return;
    }
    setError(null);
    try {
      await generateReport.mutateAsync({ organizationId, reportType, subject: subject.trim() });
      toast.success("Report generated");
      setSubject("");
    } catch (submitError) {
      const description = submitError instanceof ApiRequestError ? submitError.message : "Please try again.";
      toast.danger("Could not generate report", description);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-3">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="ai-report-type">Type</Label>
        <Select id="ai-report-type" value={reportType} onChange={(event) => setReportType(event.target.value as AiReportTypeValue)} className="w-44">
          {AI_REPORT_TYPES.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </Select>
      </div>

      <div className="flex min-w-[16rem] flex-1 flex-col gap-1.5">
        <Label htmlFor="ai-report-subject">Subject</Label>
        <Input id="ai-report-subject" value={subject} onChange={(event) => setSubject(event.target.value)} placeholder="What should this report cover?" />
      </div>

      {error && <p className="text-danger w-full text-sm">{error}</p>}

      <Button type="submit" loading={generateReport.isPending} disabled={!subject.trim()}>
        Generate
      </Button>
    </form>
  );
}
