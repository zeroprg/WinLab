import { useRef, useState, useCallback, useEffect } from "react";
import { API_BASE, apiUrl } from "../services/api";
import OpenAIWebRTCClient from "../webrtc/OpenAIWebRTCClient";
import { useLocale } from "../contexts/LocaleContext";
import { useUserId } from "../contexts/UserContext";
import { type Message, generateMessageId } from "../types/chat";

export interface UseAudioChatResult {
  recordingError?: string;
  permissionError?: string;
  statusMessage: string;
  isVoiceConnected: boolean;
  isVoiceConnecting: boolean;
  startVoiceChat: () => Promise<void>;
  stopVoiceChat: () => void;
}

export default function useAudioChat(
  addMessage: (msg: Message) => void,
  appendToMessage: (id: string, delta: string) => void,
  insertBeforeMessage: (anchorId: string, msg: Message) => void,
  setMessageContent: (id: string, content: string) => void,
): UseAudioChatResult {
  const userId = useUserId();
  const { t, locale } = useLocale();

  const [recordingError, setRecordingError] = useState<string | undefined>();
  const [permissionError, setPermissionError] = useState<string | undefined>();
  const [statusMessage, setStatusMessage] = useState(() => t("voiceReady"));

  const [isVoiceConnected, setIsVoiceConnected] = useState(false);
  const [isVoiceConnecting, setIsVoiceConnecting] = useState(false);

  useEffect(() => {
    if (!isVoiceConnected && !isVoiceConnecting) {
      setStatusMessage(t("voiceReady"));
    }
  }, [locale, t, isVoiceConnected, isVoiceConnecting]);
  const agentTranscriptRef = useRef("");
  const userTranscriptRef = useRef("");
  const currentAssistantMsgId = useRef<string | null>(null);
  const rtcRef = useRef<OpenAIWebRTCClient | null>(null);
  /** Matches server interview_sessions row for this voice call (from /api/realtime/session). */
  const realtimeSessionIdRef = useRef<string | null>(null);
  /** Ordered list of completed turns for saving to DB (preserves question→answer order). */
  const turnsRef = useRef<Array<{ role: string; text: string }>>([]);
  /** Accumulates current assistant response text until the turn is finalized. */
  const pendingAssistantTextRef = useRef("");

  const addMessageRef = useRef(addMessage);
  addMessageRef.current = addMessage;
  const appendRef = useRef(appendToMessage);
  appendRef.current = appendToMessage;
  const insertBeforeRef = useRef(insertBeforeMessage);
  insertBeforeRef.current = insertBeforeMessage;
  const setContentRef = useRef(setMessageContent);
  setContentRef.current = setMessageContent;

  const startVoiceChat = useCallback(async () => {
    if (isVoiceConnected || isVoiceConnecting) return;

    setIsVoiceConnecting(true);
    setRecordingError(undefined);
    setPermissionError(undefined);
    agentTranscriptRef.current = "";
    userTranscriptRef.current = "";
    currentAssistantMsgId.current = null;
    realtimeSessionIdRef.current = null;
    turnsRef.current = [];
    pendingAssistantTextRef.current = "";
    setStatusMessage(t("voiceConnecting"));

    try {
      const client = new OpenAIWebRTCClient();
      rtcRef.current = client;

      const greetingScheduledRef = { current: false };

      client.setEventHandler((event) => {
        const t = event.type as string;

        // Defer first response so mic/session + VAD are ready; avoids clipped opening and self-echo races.
        if ((t === "session.created" || t === "session.updated") && !greetingScheduledRef.current) {
          greetingScheduledRef.current = true;
          const delayMs = import.meta.env.MODE === "test" ? 0 : 400;
          window.setTimeout(() => {
            client.sendEvent({ type: "response.create" });
          }, delayMs);
        }

        if (t === "response.created") {
          if (agentTranscriptRef.current) {
            agentTranscriptRef.current += "\n";
          }
          pendingAssistantTextRef.current = "";
          const msgId = generateMessageId();
          currentAssistantMsgId.current = msgId;
          addMessageRef.current({
            id: msgId,
            role: "assistant",
            content: "",
            timestamp: Date.now(),
          });
        }

        if (
          t === "response.output_text.delta" ||
          t === "response.output_audio_transcript.delta"
        ) {
          const delta = (event.delta as string) ?? "";
          agentTranscriptRef.current += delta;
          pendingAssistantTextRef.current += delta;
          if (currentAssistantMsgId.current) {
            appendRef.current(currentAssistantMsgId.current, delta);
          }
        }

        if (t === "response.output_audio_transcript.done") {
          const full = (event.transcript as string) ?? "";
          const id = currentAssistantMsgId.current;
          if (full && id) {
            agentTranscriptRef.current = full;
            pendingAssistantTextRef.current = full;
            setContentRef.current(id, full);
          }
          if (pendingAssistantTextRef.current.trim()) {
            turnsRef.current.push({ role: "assistant", text: pendingAssistantTextRef.current.trim() });
          }
          pendingAssistantTextRef.current = "";
        }

        if (t === "conversation.item.input_audio_transcription.completed") {
          const text = (event.transcript as string) ?? "";
          if (text) {
            if (userTranscriptRef.current) {
              userTranscriptRef.current += "\n";
            }
            userTranscriptRef.current += text;
            turnsRef.current.push({ role: "user", text: text.trim() });
            const userMsg: Message = {
              id: generateMessageId(),
              role: "user",
              content: text,
              timestamp: Date.now(),
            };
            if (currentAssistantMsgId.current) {
              insertBeforeRef.current(currentAssistantMsgId.current, userMsg);
            } else {
              addMessageRef.current(userMsg);
            }
          }
        }
      });

      const endpoint = API_BASE
        ? `${API_BASE.replace(/\/$/, "")}/api/realtime/session`
        : "/api/realtime/session";

      const { session_id } = await client.connect(endpoint, userId, locale);
      realtimeSessionIdRef.current = session_id ?? null;
      setIsVoiceConnected(true);
      setStatusMessage(t("voiceConnected"));
    } catch (err: any) {
      setRecordingError(err?.message || "Voice connection failed");
      setStatusMessage(t("voiceFailed"));
      rtcRef.current?.disconnect();
      rtcRef.current = null;
    } finally {
      setIsVoiceConnecting(false);
    }
  }, [isVoiceConnected, isVoiceConnecting, userId, setMessageContent, t]);

  const stopVoiceChat = useCallback(async () => {
    // Flush any pending assistant text that wasn't finalized by a "done" event
    if (pendingAssistantTextRef.current.trim()) {
      turnsRef.current.push({ role: "assistant", text: pendingAssistantTextRef.current.trim() });
      pendingAssistantTextRef.current = "";
    }

    const turns = [...turnsRef.current];
    rtcRef.current?.disconnect();
    rtcRef.current = null;
    setIsVoiceConnected(false);
    currentAssistantMsgId.current = null;
    setStatusMessage(t("voiceSaving"));

    const saveMessage = async (text: string, role: string) => {
      const sid = realtimeSessionIdRef.current;
      const res = await fetch(apiUrl("/api/message"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId,
          text,
          role,
          locale,
          no_reply: true,
          ...(sid ? { session_id: sid } : {}),
        }),
      });
      if (!res.ok) {
        const detail = await res.text().catch(() => "");
        throw new Error(`Save failed (${res.status}): ${detail}`);
      }
    };

    try {
      for (const turn of turns) {
        await saveMessage(turn.text, turn.role);
      }
      setStatusMessage(t("voiceEnded"));
    } catch (err: any) {
      console.error("Failed to save voice transcript:", err);
      setRecordingError("Failed to save conversation transcript");
      setStatusMessage(t("voiceEndedNoSave"));
    }

    agentTranscriptRef.current = "";
    userTranscriptRef.current = "";
    turnsRef.current = [];
    pendingAssistantTextRef.current = "";
    realtimeSessionIdRef.current = null;
  }, [userId, t]);

  return {
    recordingError,
    permissionError,
    statusMessage,
    isVoiceConnected,
    isVoiceConnecting,
    startVoiceChat,
    stopVoiceChat,
  };
}
