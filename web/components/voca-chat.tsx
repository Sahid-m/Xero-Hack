"use client";

import { useChat } from "@ai-sdk/react";
import {
  DefaultChatTransport,
  lastAssistantMessageIsCompleteWithApprovalResponses,
  type ToolUIPart,
  type UIMessage,
} from "ai";
import {
  CheckCircle2,
  Link2,
  Mic,
  RotateCcw,
  Send,
  Sparkles,
  Square,
  User,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AgentActivity } from "./agent-activity";
import { MessageContent } from "./message-content";
import { ToolCallCard } from "./tool-call-card";
import {
  clearChat,
  getLegacySessionIds,
  getOrCreateConnectionId,
  getOrCreateSessionId,
  loadMessages,
  saveMessages,
} from "@/lib/storage";

const STARTERS = [
  "What can you access from my Xero account?",
  "How much am I owed right now?",
  "Show me this month's profit and loss.",
  "List my unpaid bills.",
];

function useConnectionId(): string | null {
  const [connectionId, setConnectionId] = useState<string | null>(null);
  useEffect(() => setConnectionId(getOrCreateConnectionId()), []);
  return connectionId;
}

function useSessionId(): string | null {
  const [sessionId, setSessionId] = useState<string | null>(null);
  useEffect(() => setSessionId(getOrCreateSessionId()), []);
  return sessionId;
}

function VocaChatInner({
  sessionId,
  connectionId,
  initialMessages,
}: {
  sessionId: string;
  connectionId: string;
  initialMessages: UIMessage[];
}) {
  const [input, setInput] = useState("");
  const [xeroConnected, setXeroConnected] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const checkXeroStatus = useCallback(async () => {
    const legacy = getLegacySessionIds(connectionId, sessionId);
    const params = new URLSearchParams({
      connection_id: connectionId,
      legacy_session_ids: legacy.join(","),
    });
    const res = await fetch(`/api/xero/status?${params}`);
    const data = await res.json();
    setXeroConnected(Boolean(data.connected));
  }, [connectionId, sessionId]);

  useEffect(() => {
    checkXeroStatus();
    const params = new URLSearchParams(window.location.search);
    if (params.get("xero") === "connected") {
      window.history.replaceState({}, "", "/");
      checkXeroStatus();
    }
  }, [checkXeroStatus]);

  const legacySessionIds = useMemo(
    () => getLegacySessionIds(connectionId, sessionId),
    [connectionId, sessionId],
  );

  const transport = useMemo(
    () =>
      new DefaultChatTransport({
        api: "/api/chat",
        body: {
          session_id: sessionId,
          connection_id: connectionId,
          legacy_session_ids: legacySessionIds,
        },
      }),
    [sessionId, connectionId, legacySessionIds],
  );

  const {
    messages,
    sendMessage,
    setMessages,
    addToolApprovalResponse,
    status,
    error,
    stop,
  } = useChat({
    id: sessionId,
    messages: initialMessages,
    transport,
    sendAutomaticallyWhen: lastAssistantMessageIsCompleteWithApprovalResponses,
    onFinish: ({ messages: next }) => {
      void saveMessages(sessionId, next);
    },
  });

  useEffect(() => {
    if (messages.length > 0) void saveMessages(sessionId, messages);
  }, [messages, sessionId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, status]);

  const isLoading = status === "submitted" || status === "streaming";
  const sessionShort = sessionId.slice(0, 8);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || isLoading) return;
    sendMessage({ text });
    setInput("");
  };

  const handleNewChat = () => {
    void clearChat(sessionId);
    setMessages([]);
  };

  return (
    <div className="flex h-full min-h-0 flex-1">
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="shrink-0 border-b border-white/[0.06] bg-[#0a0a0c]/80 backdrop-blur-md px-4 py-3 sm:px-6">
          <div className="mx-auto flex max-w-3xl items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-xl bg-gradient-to-br from-[#13b5ea]/30 to-[#0d9488]/20 ring-1 ring-[#13b5ea]/30 shadow-lg shadow-[#13b5ea]/5">
              <Mic className="size-5 text-[#5eead4]" />
            </div>
            <div className="min-w-0 flex-1">
              <h1 className="text-base font-semibold tracking-tight text-white">Voca</h1>
              <p className="truncate text-xs text-zinc-500">
                Xero without ever opening Xero
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span
                className="hidden sm:inline rounded-md bg-zinc-900 px-2 py-1 font-mono text-[10px] text-zinc-500 ring-1 ring-white/5"
                title={sessionId}
              >
                {sessionShort}
              </span>
              {xeroConnected ? (
                <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/25 bg-emerald-500/10 px-2.5 py-1 text-xs font-medium text-emerald-400">
                  <CheckCircle2 className="size-3" />
                  Xero
                </span>
              ) : (
                <a
                  href={`/api/xero/connect?connection_id=${connectionId}`}
                  className="inline-flex items-center gap-1 rounded-full border border-[#13b5ea]/40 bg-[#13b5ea]/10 px-3 py-1 text-xs font-medium text-[#7dd3fc] hover:bg-[#13b5ea]/20 transition-colors"
                >
                  <Link2 className="size-3" />
                  Connect
                </a>
              )}
              {messages.length > 0 && (
                <button
                  type="button"
                  onClick={handleNewChat}
                  className="rounded-lg p-2 text-zinc-500 hover:bg-white/5 hover:text-zinc-300"
                  title="New chat"
                >
                  <RotateCcw className="size-4" />
                </button>
              )}
            </div>
          </div>
        </header>

        <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-6 sm:px-6">
          {messages.length === 0 ? (
            <div className="mx-auto flex max-w-lg flex-col items-center pt-12 text-center">
              <div className="mb-6 flex size-14 items-center justify-center rounded-2xl bg-gradient-to-br from-[#13b5ea]/20 to-transparent ring-1 ring-[#13b5ea]/20">
                <Sparkles className="size-7 text-[#13b5ea]" />
              </div>
              <h2 className="text-xl font-semibold text-zinc-100">
                Your Xero assistant
              </h2>
              <p className="mt-2 text-sm leading-relaxed text-zinc-500">
                Ask about your books, invoice a customer, or run a quick setup — all in
                plain English. No menus, no accounting degree required.
              </p>
              {!xeroConnected && (
                <p className="mt-4 rounded-lg border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-xs text-amber-200/90">
                  Connect Xero first so Voca can write to your books.
                </p>
              )}
              <div className="mt-8 flex w-full flex-col gap-2">
                {STARTERS.map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    onClick={() => sendMessage({ text: prompt })}
                    className="rounded-xl border border-white/[0.06] bg-zinc-900/50 px-4 py-3 text-left text-sm text-zinc-400 transition-colors hover:border-[#13b5ea]/30 hover:bg-zinc-900 hover:text-zinc-200"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="mx-auto max-w-2xl space-y-6">
              {messages.map((message) => {
                const isUser = message.role === "user";
                return (
                  <div
                    key={message.id}
                    className={`flex gap-3 ${isUser ? "flex-row-reverse" : "flex-row"}`}
                  >
                    <div
                      className={`flex size-8 shrink-0 items-center justify-center rounded-lg ${
                        isUser
                          ? "bg-teal-600/20 text-teal-300"
                          : "bg-[#13b5ea]/15 text-[#13b5ea]"
                      }`}
                    >
                      {isUser ? <User className="size-4" /> : <Mic className="size-4" />}
                    </div>
                    <div
                      className={`min-w-0 flex-1 space-y-2 ${isUser ? "items-end" : "items-start"}`}
                    >
                      {message.parts.map((part, i) => {
                        if (part.type === "text" && part.text.trim()) {
                          return (
                            <div
                              key={`${message.id}-${i}`}
                              className={`rounded-2xl px-4 py-3 text-sm ${
                                isUser
                                  ? "ml-auto max-w-[85%] bg-teal-600/15 text-teal-50 ring-1 ring-teal-500/20"
                                  : "bg-zinc-900/80 text-zinc-300 ring-1 ring-white/[0.06]"
                              }`}
                            >
                              {isUser ? (
                                part.text
                              ) : (
                                <MessageContent text={part.text} />
                              )}
                            </div>
                          );
                        }
                        if (part.type.startsWith("tool-")) {
                          return (
                            <div key={`${message.id}-${i}`} className="max-w-md">
                              <ToolCallCard
                                part={part as ToolUIPart}
                                onApprove={(id) =>
                                  addToolApprovalResponse({ id, approved: true })
                                }
                                onReject={(id) =>
                                  addToolApprovalResponse({ id, approved: false })
                                }
                              />
                            </div>
                          );
                        }
                        return null;
                      })}
                    </div>
                  </div>
                );
              })}
              {isLoading && (
                <div className="flex gap-3">
                  <div className="flex size-8 items-center justify-center rounded-lg bg-[#13b5ea]/15">
                    <Mic className="size-4 text-[#13b5ea] animate-pulse" />
                  </div>
                  <div className="flex items-center gap-1 rounded-2xl bg-zinc-900/80 px-4 py-3 ring-1 ring-white/[0.06]">
                    <span className="size-1.5 animate-bounce rounded-full bg-zinc-500 [animation-delay:0ms]" />
                    <span className="size-1.5 animate-bounce rounded-full bg-zinc-500 [animation-delay:150ms]" />
                    <span className="size-1.5 animate-bounce rounded-full bg-zinc-500 [animation-delay:300ms]" />
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {error && (
          <div className="mx-auto mb-2 max-w-2xl rounded-xl border border-red-500/25 bg-red-500/10 px-4 py-2.5 text-sm text-red-300">
            {error.message}
          </div>
        )}

        <form
          onSubmit={handleSubmit}
          className="shrink-0 border-t border-white/[0.06] bg-[#0a0a0c]/90 p-4 backdrop-blur-md sm:px-6"
        >
          <div className="mx-auto flex max-w-2xl gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={
                xeroConnected
                  ? "Ask anything or tell Voca what to do…"
                  : "Ask a question, or connect Xero for live data…"
              }
              disabled={isLoading}
              className="flex-1 rounded-xl border border-white/[0.08] bg-zinc-900/80 px-4 py-3 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-[#13b5ea]/40 focus:outline-none focus:ring-2 focus:ring-[#13b5ea]/20 disabled:opacity-50"
            />
            {isLoading ? (
              <button
                type="button"
                onClick={stop}
                className="flex size-11 items-center justify-center rounded-xl border border-white/10 bg-zinc-800 text-zinc-300 hover:bg-zinc-700"
              >
                <Square className="size-4" />
              </button>
            ) : (
              <button
                type="submit"
                disabled={!input.trim()}
                className="flex size-11 items-center justify-center rounded-xl bg-gradient-to-br from-[#13b5ea] to-[#0d9488] text-white shadow-lg shadow-[#13b5ea]/20 hover:opacity-90 disabled:opacity-40"
              >
                <Send className="size-4" />
              </button>
            )}
          </div>
        </form>
      </div>

      <div className="hidden w-72 shrink-0 border-l border-white/[0.06] bg-[#08080a]/50 xl:block xl:w-80">
        <AgentActivity
          messages={messages}
          onApprove={(id) => addToolApprovalResponse({ id, approved: true })}
          onReject={(id) => addToolApprovalResponse({ id, approved: false })}
        />
      </div>
    </div>
  );
}

export function VocaChat() {
  const sessionId = useSessionId();
  const connectionId = useConnectionId();
  const [initialMessages, setInitialMessages] = useState<UIMessage[] | null>(null);

  useEffect(() => {
    if (!sessionId) return;
    let cancelled = false;
    loadMessages(sessionId).then((msgs) => {
      if (!cancelled) setInitialMessages(msgs);
    });
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  if (!sessionId || !connectionId || initialMessages === null) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <div className="flex items-center gap-2 text-sm text-zinc-500">
          <span className="size-2 animate-pulse rounded-full bg-[#13b5ea]" />
          Loading session…
        </div>
      </div>
    );
  }

  return (
    <VocaChatInner
      sessionId={sessionId}
      connectionId={connectionId}
      initialMessages={initialMessages}
    />
  );
}
