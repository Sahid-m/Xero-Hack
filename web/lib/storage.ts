import type { UIMessage } from "ai";

const SESSION_KEY = "voca_session_id";
const CONNECTION_KEY = "voca_connection_id";

/** Stable id for Xero OAuth — survives chat session changes. */
export function getOrCreateConnectionId(): string {
  if (typeof window === "undefined") return "";
  let id = localStorage.getItem(CONNECTION_KEY);
  if (!id) {
    id = localStorage.getItem(SESSION_KEY) || crypto.randomUUID();
    localStorage.setItem(CONNECTION_KEY, id);
  }
  return id;
}

/** Chat session id — message history and setup interview state. */
export function getOrCreateSessionId(): string {
  if (typeof window === "undefined") return "";
  let id = localStorage.getItem(SESSION_KEY);
  if (!id) {
    id = getOrCreateConnectionId();
    localStorage.setItem(SESSION_KEY, id);
  }
  return id;
}

/** Other session ids that may hold a prior Xero connection (for migration). */
export function getLegacySessionIds(connectionId: string, sessionId: string): string[] {
  if (typeof window === "undefined") return [];
  const ids = new Set<string>();
  if (sessionId && sessionId !== connectionId) ids.add(sessionId);
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (!key?.startsWith("voca_messages_")) continue;
    const legacyId = key.slice("voca_messages_".length);
    if (legacyId && legacyId !== connectionId) ids.add(legacyId);
  }
  return [...ids];
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
