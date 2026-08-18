"use client";

import { ThumbsDown, ThumbsUp } from "lucide-react";
import { useState } from "react";

import { ApiRequestError } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/forms/textarea";
import { useSubmitFeedback } from "@/features/ai-assistant/hooks/use-insights";
import type { FeedbackRatingValue } from "@/features/ai-assistant/types";
import { toast } from "@/state/toast-store";
import { cn } from "@/utils/cn";

/**
 * Per-assistant-message thumbs up/down (§21-style feedback affordance,
 * matching every other feature's "rate this" pattern). `POST
 * /ai/feedback` has no read endpoint, so once submitted this renders
 * the chosen rating from purely local state — a page refresh loses
 * that it was already rated, which is honest given the backend gives
 * no way to know otherwise.
 */
export function FeedbackButtons({ organizationId, messageId }: { organizationId: string; messageId: string }) {
  const [submitted, setSubmitted] = useState<FeedbackRatingValue | null>(null);
  const [showComment, setShowComment] = useState(false);
  const [comment, setComment] = useState("");
  const submitFeedback = useSubmitFeedback();

  async function submit(rating: FeedbackRatingValue, withComment?: string) {
    try {
      await submitFeedback.mutateAsync({ organizationId, messageId, rating, comment: withComment || undefined });
      setSubmitted(rating);
      setShowComment(false);
      toast.success("Feedback recorded");
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not record feedback", message);
    }
  }

  if (submitted) {
    return <p className="text-muted-foreground text-xs">{submitted === "positive" ? "Marked helpful" : "Marked not helpful"} — thanks.</p>;
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={() => submit("positive")}
          disabled={submitFeedback.isPending}
          aria-label="Helpful"
          className={cn("text-muted-foreground hover:text-success rounded p-1", "focus-visible:ring-ring focus-visible:ring-2 focus-visible:outline-none")}
        >
          <ThumbsUp className="size-3.5" aria-hidden="true" />
        </button>
        <button
          type="button"
          onClick={() => setShowComment(true)}
          disabled={submitFeedback.isPending}
          aria-label="Not helpful"
          className={cn("text-muted-foreground hover:text-danger rounded p-1", "focus-visible:ring-ring focus-visible:ring-2 focus-visible:outline-none")}
        >
          <ThumbsDown className="size-3.5" aria-hidden="true" />
        </button>
      </div>

      {showComment && (
        <div className="flex flex-col gap-1.5">
          <Textarea
            value={comment}
            onChange={(event) => setComment(event.target.value)}
            placeholder="What went wrong? (optional)"
            className="min-h-16 text-xs"
            aria-label="Feedback comment"
          />
          <div className="flex gap-1.5">
            <Button variant="outline" onClick={() => submit("negative", comment)} loading={submitFeedback.isPending} className="h-7 px-2 text-xs">
              Submit
            </Button>
            <Button variant="ghost" onClick={() => setShowComment(false)} className="h-7 px-2 text-xs">
              Cancel
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
