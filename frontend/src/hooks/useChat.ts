import { useCallback, useEffect, useState, useRef } from "react";
import type React from "react";
import { type Message, generateMessageId } from "../types/chat";
import { sendChatRequest } from "../services/api";
import { API_BASE } from "../services/api";
import { useLocale } from "../contexts/LocaleContext";
import { useUserId } from "../contexts/UserContext";

export interface UseChatResult {
  messages: Message[];
  input: string;
  setInput: (value: string) => void;
  loading: boolean;
  sendMessage: (e?: React.FormEvent) => Promise<void>;
  sendText: (text: string, opts?: { hidden?: boolean }) => Promise<void>;
  addMessage: (msg: Message) => void;
  appendToMessage: (id: string, delta: string) => void;
  insertBeforeMessage: (anchorId: string, msg: Message) => void;
  setMessageContent: (id: string, content: string) => void;
  clearMessages: () => void;
  connected?: boolean;
}

export default function useChat(): UseChatResult {
  const userId = useUserId();
  const { t, locale } = useLocale();
  const greetingMsgIdRef = useRef<string | null>(null);
  const [messages, setMessages] = useState<Message[]>(() => {
    const id = generateMessageId();
    greetingMsgIdRef.current = id;
    return [
      {
        id,
        role: "assistant",
        content: t("chatGreeting"),
        timestamp: Date.now(),
      },
    ];
  });

  useEffect(() => {
    const gid = greetingMsgIdRef.current;
    if (!gid) return;
    setMessages((prev) => {
      if (prev.length !== 1 || prev[0].id !== gid || prev[0].role !== "assistant") {
        return prev;
      }
      return [{ ...prev[0], content: t("chatGreeting") }];
    });
  }, [locale, t]);

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const messagesRef = useRef<Message[]>(messages);

  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  useEffect(() => {
    // Try to open a WebSocket connection if API_BASE is configured
    if (!API_BASE) return;

    try {
      const base = API_BASE.replace(/\/$/, "");
      // Derive ws(s) scheme from http(s)
      const wsScheme = base.startsWith("https") ? "wss" : "ws";
      const url = `${wsScheme}://${base.replace(/^https?:\/\//, "")}/ws/${encodeURIComponent(userId)}`;
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => setConnected(true);
      ws.onclose = () => setConnected(false);
      ws.onerror = () => setConnected(false);

      ws.onmessage = (evt) => {
        try {
          const d = JSON.parse(evt.data);
          if (d?.type === "message" && d?.data) {
            setMessages((m) => [
              ...m,
              {
                id: generateMessageId(),
                role: d.data.role || "assistant",
                content: d.data.text || "",
                timestamp: Date.now(),
              },
            ]);
          }
        } catch (e) {
          // ignore non-JSON
        }
      };

      return () => {
        try {
          if (wsRef.current && wsRef.current.readyState === 1) {
            wsRef.current.close();
          }
        } catch (e) {
          // ignore
        }
        wsRef.current = null;
      };
    } catch (e) {
      // ignore websocket setup errors and fall back to HTTP
      setConnected(false);
    }
  }, [userId]);

  async function sendText(text: string, opts?: { hidden?: boolean }) {
    if (!text || loading) return;
    const userMessage: Message = {
      id: generateMessageId(),
      role: "user",
      content: text,
      timestamp: Date.now(),
    };

    if (!opts?.hidden) {
      setMessages((m) => [...m, userMessage]);
    }
    setLoading(true);

    const convo = [...messagesRef.current, userMessage];

    try {
      const replyText = await sendChatRequest(convo, userId, locale);

      setMessages((m) => [
        ...m,
        {
          id: generateMessageId(),
          role: "assistant",
          content: replyText,
          timestamp: Date.now(),
        },
      ]);
    } catch (err: any) {
      setMessages((m) => [
        ...m,
        {
          id: generateMessageId(),
          role: "assistant",
          content: `⚠️ Error: ${err?.message || err}`,
          timestamp: Date.now(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  async function sendMessage(e?: React.FormEvent) {
    e?.preventDefault();
    const text = input.trim();
    if (!text) return;
    setInput("");
    await sendText(text);
  }

  const addMessage = useCallback((msg: Message) => {
    setMessages((prev) => [...prev, msg]);
  }, []);

  const appendToMessage = useCallback((id: string, delta: string) => {
    setMessages((prev) =>
      prev.map((m) => (m.id === id ? { ...m, content: m.content + delta } : m)),
    );
  }, []);

  const insertBeforeMessage = useCallback((anchorId: string, msg: Message) => {
    setMessages((prev) => {
      const idx = prev.findIndex((m) => m.id === anchorId);
      if (idx === -1) return [...prev, msg];
      const copy = [...prev];
      copy.splice(idx, 0, msg);
      return copy;
    });
  }, []);

  const setMessageContent = useCallback((id: string, content: string) => {
    setMessages((prev) =>
      prev.map((m) => (m.id === id ? { ...m, content } : m)),
    );
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
  }, []);

  return {
    messages,
    input,
    setInput,
    loading,
    sendMessage,
    sendText,
    addMessage,
    appendToMessage,
    insertBeforeMessage,
    setMessageContent,
    clearMessages,
    connected,
  };
}
