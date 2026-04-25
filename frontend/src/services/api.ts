// src/services/api.ts
import { type CardType, type Message, type MessageMetadata } from "../types/chat";

export const API_BASE = (import.meta.env.VITE_API_BASE as string) || "";

export const TEST_FETCH =
  String(import.meta.env.VITE_TEST_FETCH || "").toLowerCase() === "true";

export function apiUrl(path: string): string {
  const base = (API_BASE || "").replace(/\/+$/, "");
  const tail = path.startsWith("/") ? path : `/${path}`;
  return `${base}${tail}`;
}

/**
 * Wrapper around fetch that injects the JWT Authorization header
 * from localStorage if a token is present.
 */
export function authFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const token = localStorage.getItem("chat_auth_token") || "";
  const headers = new Headers(init?.headers);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return fetch(input, { ...init, headers });
}

interface ChatApiMessage {
  text?: string;
  [key: string]: unknown;
}

export interface ChatApiResponse {
  reply?: string;
  card_type?: CardType;
  metadata?: MessageMetadata;
  message?: ChatApiMessage;
  [key: string]: unknown;
}

interface TestPostResponse {
  id?: number;
  title?: string;
  body?: string;
  userId?: number;
  [key: string]: unknown;
}


export async function sendChatRequest(messages: Message[], userId = "web", locale = ""): Promise<string> {
  const lastUserMessage =
    [...messages].reverse().find((m) => m.role === "user")?.content ?? "";

  async function retryFetch(input: RequestInfo, init?: RequestInit, attempts = 3, delay = 300) {
    let lastErr: any;
    for (let i = 0; i < attempts; i++) {
      try {
        const r = await fetch(input, init);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r;
      } catch (e) {
        lastErr = e;
        // exponential backoff
        await new Promise((res) => setTimeout(res, delay * Math.pow(2, i)));
      }
    }
    throw lastErr;
  }

  if (TEST_FETCH) {
    // If a local API base is provided, prefer calling the local backend
    // in test mode so developers can exercise the real server without
    // hitting the external jsonplaceholder service.
    if (API_BASE) {
      const res = await retryFetch(apiUrl("/api/message"), {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Test-Fetch": "1" },
        body: JSON.stringify({ user_id: userId, role: "user", text: lastUserMessage, locale }),
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      const data = (await res.json()) as ChatApiResponse | string;
      if (typeof data === "string") return data;
      return data?.reply ?? (data?.message && data.message.text) ?? JSON.stringify(data);
    }

    // Fallback to external jsonplaceholder if no local API is configured
    const res = await retryFetch("https://jsonplaceholder.typicode.com/posts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: lastUserMessage || "Test message",
        body: `Echo: ${lastUserMessage}`,
        userId: 1,
      }),
    });

    const status = res.status;
    const data = (await res.json()) as TestPostResponse;

    return `Test fetch OK (HTTP ${status}). id=${data?.id}; title="${data?.title}"`;
  }

  const res = await retryFetch(apiUrl("/api/message"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: userId,
      role: "user",
      text: lastUserMessage,
      locale,
    }),
  });

  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }

  const data = (await res.json()) as ChatApiResponse | string;

  if (typeof data === "string") {
    return data;
  }

  const reply =
    data?.reply ??
    (data?.message && data.message.text) ??
    JSON.stringify(data);

  return reply;
}

export interface ChatMessageResult {
  text: string;
  card_type?: CardType;
  metadata?: MessageMetadata;
}

/**
 * Full chat API call returning text + card_type + metadata.
 * Used by the WinLab chat widget for structured card rendering.
 */
export async function sendChatMessage(
  userText: string,
  userId: string,
  locale: string,
): Promise<ChatMessageResult> {
  const res = await fetch(apiUrl("/api/message"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, role: "user", text: userText, locale }),
  });

  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }

  const data = (await res.json()) as ChatApiResponse;
  return {
    text: data.reply ?? data?.message?.text ?? "…",
    card_type: data.card_type,
    metadata: data.metadata,
  };
}


interface AudioIngestResponse {
  ingest_id: string;
  status: string;
  ingest_at: string;
  [key: string]: unknown;
}

interface AudioStatusResponse {
  status: string;
  transcript?: string;
  [key: string]: unknown;
}

export async function uploadAudioBlob(
  blob: Blob,
  userId: string,
  durationSeconds?: number,
  metadata?: string,
): Promise<AudioIngestResponse> {
  const form = new FormData();
  form.append("user_id", userId);
  form.append("audio", blob, "recording.webm");
  if (durationSeconds !== undefined) {
    form.append("duration", durationSeconds.toString());
  }
  if (metadata) {
    form.append("metadata", metadata);
  }

  const res = await fetch(apiUrl("/api/audio"), {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }

  return (await res.json()) as AudioIngestResponse;
}

export async function fetchAudioStatus(ingestId: string): Promise<AudioStatusResponse> {
  const res = await fetch(apiUrl(`/api/audio/${ingestId}`));
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  return (await res.json()) as AudioStatusResponse;
}


export function getChatStatusRight(): string {
  return TEST_FETCH
    ? "→ POST https://jsonplaceholder.typicode.com/posts"
    : `→ ${API_BASE ? apiUrl("/api/message") : "(VITE_API_BASE is not set)"}`;
}
