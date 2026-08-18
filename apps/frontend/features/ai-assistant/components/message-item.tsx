import { Bot, Terminal, User, Wrench } from "lucide-react";

import { CitationsList } from "@/features/ai-assistant/components/citations-list";
import { FeedbackButtons } from "@/features/ai-assistant/components/feedback-buttons";
import type { Message } from "@/features/ai-assistant/types";
import { cn } from "@/utils/cn";

const ROLE_META = {
  user: { label: "You", icon: User, align: "justify-end", bubble: "bg-primary text-primary-foreground" },
  assistant: { label: "Assistant", icon: Bot, align: "justify-start", bubble: "bg-surface-elevated border border-border" },
  system: { label: "System", icon: Terminal, align: "justify-start", bubble: "bg-muted text-muted-foreground text-xs italic" },
  tool: { label: "Tool", icon: Wrench, align: "justify-start", bubble: "bg-muted text-muted-foreground text-xs" },
} as const;

/** One message bubble, role-distinct per §18. `content` is always
 * plain text (see `Message`'s own docstring) — rendered with
 * `whitespace-pre-wrap` so real newlines the model produced still
 * read correctly, without interpreting markdown/HTML the backend
 * never promises to sanitize. */
export function MessageItem({ organizationId, message }: { organizationId: string; message: Message }) {
  const meta = ROLE_META[message.role];
  const Icon = meta.icon;

  return (
    <div className={cn("flex gap-2", meta.align)}>
      {message.role !== "user" && (
        <div className="bg-muted flex size-7 shrink-0 items-center justify-center rounded-full">
          <Icon className="size-4" aria-hidden="true" />
        </div>
      )}
      <div className={cn("flex max-w-[80%] flex-col gap-1 rounded-lg px-3 py-2 text-sm", meta.bubble)}>
        <p className="whitespace-pre-wrap">{message.content}</p>

        {message.role === "assistant" && (
          <>
            <CitationsList citations={message.citations} />
            <div className="mt-1">
              <FeedbackButtons organizationId={organizationId} messageId={message.id} />
            </div>
          </>
        )}

        {message.role === "assistant" && (message.provider || message.model) && (
          <p className="text-muted-foreground text-[11px]">
            {message.provider}
            {message.provider && message.model ? " / " : ""}
            {message.model}
          </p>
        )}
      </div>
    </div>
  );
}
