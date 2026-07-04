import type { UIMessage } from "ai";

const SESSION_KEY = "voca_session_id";

export function getOrCreateSessionId(): string {
  if (typeof window === "undefined") return "";
  let id = localStorage.getItem(SESSION_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(SESSION_KEY, id);
  }
  return id;
}

function messagesKey(sessionId: string) {
  return `voca_messages_${sessionId}`;
}

export function loadMessages(sessionId: string): UIMessage[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(messagesKey(sessionId));
    return raw ? (JSON.parse(raw) as UIMessage[]) : [];
  } catch {
    return [];
  }
}

export function saveMessages(sessionId: string, messages: UIMessage[]) {
  if (typeof window === "undefined") return;
  localStorage.setItem(messagesKey(sessionId), JSON.stringify(messages));
}

export function clearChat(sessionId: string) {
  localStorage.removeItem(messagesKey(sessionId));
}
