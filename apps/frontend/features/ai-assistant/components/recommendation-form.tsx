"use client";

import { useState } from "react";

import { ApiRequestError } from "@/api/client";
import { Input } from "@/components/forms/input";
import { Label } from "@/components/forms/label";
import { Select } from "@/components/forms/select";
import { Button } from "@/components/ui/button";
import { useGenerateRecommendation } from "@/features/ai-assistant/hooks/use-insights";
import { RECOMMENDATION_TYPES, type RecommendationTypeValue } from "@/features/ai-assistant/types";
import { toast } from "@/state/toast-store";

export function RecommendationForm({ organizationId }: { organizationId: string }) {
  const [recommendationType, setRecommendationType] = useState<RecommendationTypeValue>("automation");
  const [subject, setSubject] = useState("");
  const [error, setError] = useState<string | null>(null);
  const generateRecommendation = useGenerateRecommendation();

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!subject.trim()) {
      setError("Subject is required.");
      return;
    }
    setError(null);
    try {
      await generateRecommendation.mutateAsync({ organizationId, recommendationType, subject: subject.trim() });
      toast.success("Recommendation generated");
      setSubject("");
    } catch (submitError) {
      const description = submitError instanceof ApiRequestError ? submitError.message : "Please try again.";
      toast.danger("Could not generate recommendation", description);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-3">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="recommendation-type">Type</Label>
        <Select
          id="recommendation-type"
          value={recommendationType}
          onChange={(event) => setRecommendationType(event.target.value as RecommendationTypeValue)}
          className="w-40"
        >
          {RECOMMENDATION_TYPES.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </Select>
      </div>

      <div className="flex min-w-[16rem] flex-1 flex-col gap-1.5">
        <Label htmlFor="recommendation-subject">Subject</Label>
        <Input id="recommendation-subject" value={subject} onChange={(event) => setSubject(event.target.value)} placeholder="What should this recommendation address?" />
      </div>

      {error && <p className="text-danger w-full text-sm">{error}</p>}

      <Button type="submit" loading={generateRecommendation.isPending} disabled={!subject.trim()}>
        Generate
      </Button>
    </form>
  );
}
