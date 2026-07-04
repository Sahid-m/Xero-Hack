"use client";

import type { ToolUIPart, UIMessage } from "ai";
import { Activity } from "lucide-react";
import { ToolCallCard } from "./tool-call-card";

type AgentActivityProps = {
  messages: UIMessage[];
  onApprove?: (id: string) => void;
  onReject?: (id: string) => void;
};

export function AgentActivity({ messages, onApprove, onReject }: AgentActivityProps) {
  const toolParts: { key: string; part: ToolUIPart }[] = [];

  for (const message of messages) {
    if (message.role !== "assistant") continue;
    for (const part of message.parts) {
      if (part.type.startsWith("tool-")) {
        toolParts.push({
          key: `${message.id}-${(part as ToolUIPart).toolCallId}`,
          part: part as ToolUIPart,
        });
      }
    }
  }

  return (
    <aside className="flex h-full flex-col border-l border-white/10 bg-zinc-950/50">
      <div className="flex items-center gap-2 border-b border-white/10 px-4 py-3">
        <Activity className="size-4 text-teal-400" />
        <h2 className="text-sm font-semibold text-zinc-200">Agent activity</h2>
        <span className="ml-auto rounded-full bg-white/10 px-2 py-0.5 text-xs text-zinc-400">
          {toolParts.length}
        </span>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {toolParts.length === 0 ? (
          <p className="text-xs text-zinc-500 px-1 py-4 text-center leading-relaxed">
            Tool calls appear here as Voca configures Xero — contacts, invoices, VAT, and more.
          </p>
        ) : (
          toolParts.map(({ key, part }) => (
            <ToolCallCard
              key={key}
              part={part}
              compact
              onApprove={onApprove}
              onReject={onReject}
            />
          ))
        )}
      </div>
    </aside>
  );
}
