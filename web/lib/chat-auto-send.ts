import type { ToolUIPart, UIMessage } from "ai";

/** Only re-post to the backend after the user approves a write tool — not after read-only tools finish. */
export function shouldResubmitForToolApproval({
  messages,
}: {
  messages: UIMessage[];
}): boolean {
  const last = messages.at(-1);
  if (!last || last.role !== "assistant") return false;

  const toolParts = last.parts.filter(
    (part): part is ToolUIPart =>
      typeof part.type === "string" && part.type.startsWith("tool-"),
  );
  if (toolParts.length === 0) return false;

  const hasApprovalResponse = toolParts.some(
    (part) => part.state === "approval-responded",
  );
  const awaitingOutput = toolParts.some(
    (part) =>
      part.state === "approval-responded" ||
      part.state === "input-available" ||
      part.state === "input-streaming",
  );

  return hasApprovalResponse && awaitingOutput;
}
