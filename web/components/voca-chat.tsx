"use client";

import { useChat } from "@ai-sdk/react";
import {
  DefaultChatTransport,
  lastAssistantMessageIsCompleteWithApprovalResponses,
  type ToolUIPart,
} from "ai";
import { Link2, Mic, Send, Square } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AgentActivity } from "./agent-activity";
import { ToolCallCard } from "./tool-call-card";

export function VocaChat() {
  const sessionId = useMemo(() => crypto.randomUUID(), []);
  const [input, setInput] = useState("");
  const [xeroConnected, setXeroConnected] = useState(false);

  const checkXeroStatus = useCallback(async () => {
    const res = await fetch(`/api/xero/status?session_id=${sessionId}`);
    const data = await res.json();
    setXeroConnected(Boolean(data.connected));
  }, [sessionId]);

  useEffect(() => {
    checkXeroStatus();
    const params = new URLSearchParams(window.location.search);
    if (params.get("xero") === "connected") {
      setXeroConnected(true);
      window.history.replaceState({}, "", "/");
    }
  }, [checkXeroStatus]);

  const transport = useMemo(
    () =>
      new DefaultChatTransport({
        api: "/api/chat",
        body: { session_id: sessionId },
      }),
    [sessionId],
  );

  const {
    messages,
    sendMessage,
    addToolApprovalResponse,
    status,
    error,
    stop,
  } = useChat({
    transport,
    sendAutomaticallyWhen: lastAssistantMessageIsCompleteWithApprovalResponses,
  });

  const isLoading = status === "submitted" || status === "streaming";

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || isLoading) return;
    sendMessage({ text });
    setInput("");
  };

  const handleApprove = (id: string) => {
    addToolApprovalResponse({ id, approved: true });
  };

  const handleReject = (id: string) => {
    addToolApprovalResponse({ id, approved: false });
  };

  return (
    <div className="flex h-full min-h-0 flex-1">
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="shrink-0 border-b border-white/10 px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex size-9 items-center justify-center rounded-full bg-teal-500/20 ring-1 ring-teal-500/40">
              <Mic className="size-4 text-teal-400" />
            </div>
            <div>
              <h1 className="text-lg font-semibold tracking-tight text-zinc-50">
                Voca
              </h1>
              <p className="text-xs text-zinc-500">
                Xero without ever opening Xero · session{" "}
                <span className="font-mono text-zinc-600">{sessionId.slice(0, 8)}</span>
              </p>
            </div>
            <div className="ml-auto flex items-center gap-3">
              {xeroConnected ? (
                <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-xs text-emerald-400">
                  Xero connected
                </span>
              ) : (
                <a
                  href={`/api/xero/connect?session_id=${sessionId}`}
                  className="flex items-center gap-1.5 rounded-full border border-teal-500/40 bg-teal-500/10 px-3 py-1.5 text-xs font-medium text-teal-300 hover:bg-teal-500/20"
                >
                  <Link2 className="size-3.5" />
                  Connect Xero
                </a>
              )}
              <span
                className={`size-2 rounded-full ${isLoading ? "bg-teal-400 animate-pulse" : "bg-zinc-600"}`}
              />
              <span className="text-xs text-zinc-500 capitalize">{status}</span>
            </div>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto px-4 py-6 sm:px-6">
          {messages.length === 0 ? (
            <div className="mx-auto max-w-xl text-center pt-16">
              <p className="text-zinc-400 text-sm leading-relaxed">
                Try:{" "}
                <button
                  type="button"
                  className="text-teal-400 hover:underline"
                  onClick={() =>
                    sendMessage({ text: "I run a café in Bristol. Help me get set up on Xero." })
                  }
                >
                  &ldquo;I run a café in Bristol…&rdquo;
                </button>
              </p>
            </div>
          ) : (
            <div className="mx-auto max-w-2xl space-y-6">
              {messages.map((message) => (
                <div
                  key={message.id}
                  className={`flex flex-col gap-2 ${message.role === "user" ? "items-end" : "items-start"}`}
                >
                  <span className="text-[10px] uppercase tracking-wider text-zinc-600 px-1">
                    {message.role}
                  </span>
                  <div
                    className={`space-y-2 max-w-full ${
                      message.role === "user" ? "items-end" : "items-start"
                    }`}
                  >
                    {message.parts.map((part, i) => {
                      if (part.type === "text") {
                        return (
                          <div
                            key={`${message.id}-${i}`}
                            className={`rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                              message.role === "user"
                                ? "bg-teal-600/20 text-teal-50 border border-teal-500/20"
                                : "bg-zinc-900 text-zinc-200 border border-white/10"
                            }`}
                          >
                            {part.text}
                          </div>
                        );
                      }

                      if (part.type.startsWith("tool-")) {
                        return (
                          <div key={`${message.id}-${i}`} className="w-full max-w-md">
                            <ToolCallCard
                              part={part as ToolUIPart}
                              onApprove={handleApprove}
                              onReject={handleReject}
                            />
                          </div>
                        );
                      }

                      return null;
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {error && (
          <div className="mx-4 mb-2 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-2 text-sm text-red-300">
            {error.message}
          </div>
        )}

        <form
          onSubmit={handleSubmit}
          className="shrink-0 border-t border-white/10 p-4 sm:px-6"
        >
          <div className="mx-auto flex max-w-2xl gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Tell Voca about your business…"
              disabled={isLoading}
              className="flex-1 rounded-xl border border-white/10 bg-zinc-900 px-4 py-3 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-teal-500/50 focus:outline-none focus:ring-1 focus:ring-teal-500/30 disabled:opacity-50"
            />
            {isLoading ? (
              <button
                type="button"
                onClick={stop}
                className="flex items-center justify-center rounded-xl border border-white/10 bg-zinc-800 px-4 text-zinc-300 hover:bg-zinc-700"
              >
                <Square className="size-4" />
              </button>
            ) : (
              <button
                type="submit"
                disabled={!input.trim()}
                className="flex items-center justify-center rounded-xl bg-teal-600 px-4 text-white hover:bg-teal-500 disabled:opacity-40 disabled:hover:bg-teal-600"
              >
                <Send className="size-4" />
              </button>
            )}
          </div>
        </form>
      </div>

      <div className="hidden w-80 lg:block shrink-0">
        <AgentActivity
          messages={messages}
          onApprove={handleApprove}
          onReject={handleReject}
        />
      </div>
    </div>
  );
}
