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
    <aside className="flex h-full flex-col">
      <div className="flex items-center gap-2 border-b border-white/[0.06] px-4 py-3">
        <Activity className="size-4 text-[#13b5ea]" />
        <h2 className="text-sm font-medium text-zinc-300">Agent activity</h2>
        <span className="ml-auto rounded-full bg-white/5 px-2 py-0.5 text-[10px] font-medium text-zinc-500">
          {toolParts.length}
        </span>
      </div>
      <div className="flex-1 space-y-2 overflow-y-auto p-3">
        {toolParts.length === 0 ? (
          <p className="px-1 py-6 text-center text-xs leading-relaxed text-zinc-600">
            Xero tool calls appear here — contacts, invoices, VAT setup, and more.
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
