"use client";

import {
  CheckCircle2,
  ChevronDown,
  Loader2,
  ShieldAlert,
  Wrench,
  XCircle,
} from "lucide-react";
import { useState } from "react";
import type { ToolUIPart } from "ai";

const STATE_LABELS: Record<string, { label: string; color: string }> = {
  "input-streaming": { label: "Streaming args…", color: "text-amber-400" },
  "input-available": { label: "Ready to run", color: "text-sky-400" },
  "approval-requested": { label: "Awaiting approval", color: "text-orange-400" },
  "approval-responded": { label: "Approval sent", color: "text-violet-400" },
  "output-available": { label: "Complete", color: "text-emerald-400" },
  "output-error": { label: "Error", color: "text-red-400" },
  "output-denied": { label: "Denied", color: "text-zinc-500" },
};

function formatJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function StateIcon({ state }: { state: string }) {
  if (state === "input-streaming" || state === "approval-responded") {
    return <Loader2 className="size-4 animate-spin text-amber-400" />;
  }
  if (state === "output-available") {
    return <CheckCircle2 className="size-4 text-emerald-400" />;
  }
  if (state === "output-error" || state === "output-denied") {
    return <XCircle className="size-4 text-red-400" />;
  }
  if (state === "approval-requested") {
    return <ShieldAlert className="size-4 text-orange-400" />;
  }
  return <Wrench className="size-4 text-sky-400" />;
}

type ToolCallCardProps = {
  part: ToolUIPart;
  compact?: boolean;
  onApprove?: (id: string) => void;
  onReject?: (id: string) => void;
};

export function ToolCallCard({
  part,
  compact = false,
  onApprove,
  onReject,
}: ToolCallCardProps) {
  const [open, setOpen] = useState(!compact);
  const toolName = part.type.replace(/^tool-/, "");
  const meta = STATE_LABELS[part.state] ?? { label: part.state, color: "text-zinc-400" };

  return (
    <div className="rounded-lg border border-white/10 bg-zinc-900/80 overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-3 px-3 py-2.5 text-left hover:bg-white/5 transition-colors"
      >
        <StateIcon state={part.state} />
        <div className="min-w-0 flex-1">
          <p className="font-mono text-sm font-medium text-teal-300 truncate">
            {toolName}
          </p>
          <p className={`text-xs ${meta.color}`}>{meta.label}</p>
        </div>
        <ChevronDown
          className={`size-4 shrink-0 text-zinc-500 transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open && (
        <div className="border-t border-white/10 px-3 py-2 space-y-2">
          {"input" in part && part.input !== undefined && (
            <div>
              <p className="text-[10px] uppercase tracking-wider text-zinc-500 mb-1">
                Input
              </p>
              <pre className="text-xs font-mono text-zinc-300 bg-black/40 rounded p-2 overflow-x-auto max-h-40">
                {formatJson(part.input)}
              </pre>
            </div>
          )}
          {"output" in part && part.output !== undefined && (
            <div>
              <p className="text-[10px] uppercase tracking-wider text-zinc-500 mb-1">
                Output
              </p>
              <pre className="text-xs font-mono text-emerald-200/90 bg-black/40 rounded p-2 overflow-x-auto max-h-48">
                {typeof part.output === "string"
                  ? part.output
                  : formatJson(part.output)}
              </pre>
            </div>
          )}
          {"errorText" in part && part.errorText && (
            <p className="text-xs text-red-400">{part.errorText}</p>
          )}
          {part.state === "approval-requested" && part.approval && onApprove && onReject && (
            <div className="flex gap-2 pt-1">
              <button
                type="button"
                onClick={() => onReject(part.approval!.id)}
                className="flex-1 rounded-md border border-red-500/30 bg-red-500/10 px-3 py-1.5 text-xs font-medium text-red-300 hover:bg-red-500/20"
              >
                Reject
              </button>
              <button
                type="button"
                onClick={() => onApprove(part.approval!.id)}
                className="flex-1 rounded-md border border-teal-500/30 bg-teal-500/10 px-3 py-1.5 text-xs font-medium text-teal-300 hover:bg-teal-500/20"
              >
                Approve
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
