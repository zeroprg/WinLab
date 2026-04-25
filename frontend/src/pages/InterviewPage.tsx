import { useCallback, useEffect, useRef, useState } from "react";
import { apiUrl } from "../services/api";
import ChatHeader from "../components/chat/ChatHeader";
import MessageList from "../components/chat/MessageList";
import MessageInput from "../components/chat/MessageInput";
import LoadingIndicator from "../components/chat/LoadingIndicator";
import VoiceControls from "../components/chat/VoiceControls";
import useChat from "../hooks/useChat";
import useAudioChat from "../hooks/useAudioChat";
import styles from "./InterviewPage.module.css";

type Stage = "loading" | "login" | "ready" | "interview" | "finished" | "exhausted" | "error";

interface InviteInfo {
  token: string;
  position_title: string;
  candidate_email: string | null;
  attempts_remaining: number;
  time_limit_minutes: number | null;
  locale?: string;
  interview_mode?: string;
}

const i18nInterview: Record<string, Record<string, string>> = {
  ru: {
    loading: "Загрузка…",
    linkInvalid: "Ссылка недействительна",
    error: "Ошибка",
    retry: "Попробовать снова",
    enterEmail: "Введите ваши данные, чтобы начать интервью.",
    emailRequired: "Введите ваш email.",
    firstName: "Имя",
    lastName: "Фамилия",
    timeLimit: "Время на интервью:",
    min: "мин.",
    attemptsLeft: "Осталось попыток:",
    start: "Начать интервью",
    starting: "Запуск…",
    startError: "Ошибка запуска интервью.",
    connectError: "Не удалось подключиться к серверу.",
    startFailed: "Не удалось запустить интервью.",
    timeUp: "Время истекло",
    finish: "Завершить",
    finished: "Интервью завершено",
    thanks: "Спасибо за участие!",
    interview: "Интервью",
  },
  en: {
    loading: "Loading…",
    linkInvalid: "Link is invalid",
    error: "Error",
    retry: "Try again",
    enterEmail: "Enter your details to start the interview.",
    emailRequired: "Please enter your email.",
    firstName: "First name",
    lastName: "Last name",
    timeLimit: "Interview time limit:",
    min: "min.",
    attemptsLeft: "Attempts remaining:",
    start: "Start interview",
    starting: "Starting…",
    startError: "Error starting interview.",
    connectError: "Could not connect to the server.",
    startFailed: "Failed to start the interview.",
    timeUp: "Time is up",
    finish: "Finish",
    finished: "Interview completed",
    thanks: "Thank you for participating!",
    interview: "Interview",
  },
};

function formatTime(totalSeconds: number): string {
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function InterviewPage({ token }: { token: string }) {
  const [stage, setStage] = useState<Stage>("loading");
  const [invite, setInvite] = useState<InviteInfo | null>(null);
  const [email, setEmail] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const L = i18nInterview[invite?.locale || "ru"] || i18nInterview.ru;
  const [errMsg, setErrMsg] = useState("");
  const [consuming, setConsuming] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [remainingSeconds, setRemainingSeconds] = useState<number | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const inputRef = useRef<HTMLInputElement | null>(null);

  const {
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
  } = useChat();

  const audioChat = useAudioChat(
    addMessage,
    appendToMessage,
    insertBeforeMessage,
    setMessageContent,
  );

  const validate = useCallback(async () => {
    try {
      const r = await fetch(apiUrl(`/api/invites/${token}/validate`));
      if (!r.ok) {
        const body = await r.json().catch(() => ({ detail: `HTTP ${r.status}` }));
        if (r.status === 410) {
          setErrMsg(body.detail || "");
          setStage("exhausted");
        } else {
          setErrMsg(body.detail || "");
          setStage("error");
        }
        return;
      }
      const data = (await r.json()) as InviteInfo;
      setInvite(data);
      if (data.candidate_email) {
        setEmail(data.candidate_email);
      }
      setStage("login");
    } catch {
      setStage("error");
    }
  }, [token]);

  useEffect(() => {
    void validate();
  }, [validate]);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  const startInterview = async () => {
    if (!email.trim()) {
      setErrMsg(L.emailRequired);
      return;
    }
    setErrMsg("");
    setConsuming(true);
    try {
      const r = await fetch(apiUrl(`/api/invites/${token}/consume`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email.trim(),
          first_name: firstName.trim() || undefined,
          last_name: lastName.trim() || undefined,
        }),
      });
      if (!r.ok) {
        const body = await r.json().catch(() => ({ detail: `HTTP ${r.status}` }));
        setErrMsg(body.detail || L.startError);
        return;
      }
      const consumeData = await r.json();
      setSessionId(consumeData.session_id || null);
      localStorage.setItem("chat_user_id", email.trim().toLowerCase());
      const displayName = [firstName.trim(), lastName.trim()].filter(Boolean).join(" ") || email.trim().toLowerCase();
      localStorage.setItem("chat_display_name", displayName);

      if (invite?.time_limit_minutes) {
        const totalSec = Math.round(invite.time_limit_minutes * 60);
        setRemainingSeconds(totalSec);
        timerRef.current = setInterval(() => {
          setRemainingSeconds((prev) => {
            if (prev === null || prev <= 1) {
              if (timerRef.current) clearInterval(timerRef.current);
              return 0;
            }
            return prev - 1;
          });
        }, 1000);
      }

      setStage("interview");
      clearMessages();
      void sendText("[start]", { hidden: true });
    } catch {
      setErrMsg(L.startFailed);
    } finally {
      setConsuming(false);
    }
  };

  const endInterview = async () => {
    if (!sessionId) return;
    try {
      await fetch(apiUrl(`/api/sessions/${sessionId}/complete`), {
        method: "POST",
      });
    } catch {
      // ignore – best effort
    }
    if (timerRef.current) clearInterval(timerRef.current);
    setStage("finished");
  };

  // Auto-end when time runs out
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (remainingSeconds === 0 && stage === "interview") {
      void endInterview();
    }
  }, [remainingSeconds]);

  if (stage === "finished") {
    return (
      <div className={styles.wrapper}>
        <div className={styles.statusCard}>
          <p className={styles.statusTitle}>{L.finished}</p>
          <p className={styles.statusText}>{L.thanks}</p>
        </div>
      </div>
    );
  }

  if (stage === "loading") {
    return (
      <div className={styles.wrapper}>
        <div className={styles.statusCard}>
          <p className={styles.statusTitle}>{L.loading}</p>
        </div>
      </div>
    );
  }

  if (stage === "exhausted") {
    return (
      <div className={styles.wrapper}>
        <div className={styles.statusCard}>
          <p className={styles.statusTitle}>{L.linkInvalid}</p>
          {errMsg ? <p className={styles.statusText}>{errMsg}</p> : null}
        </div>
      </div>
    );
  }

  if (stage === "error") {
    return (
      <div className={styles.wrapper}>
        <div className={styles.statusCard}>
          <p className={styles.statusTitle}>{L.error}</p>
          {errMsg ? <p className={styles.statusText}>{errMsg}</p> : <p className={styles.statusText}>{L.connectError}</p>}
          <button className={styles.btnPrimary} onClick={() => void validate()}>
            {L.retry}
          </button>
        </div>
      </div>
    );
  }

  if (stage === "login" && invite) {
    return (
      <div className={styles.wrapper}>
        <div className={styles.statusCard}>
          <p className={styles.statusTitle}>{L.interview}: {invite.position_title}</p>
          <p className={styles.statusText}>
            {L.enterEmail}
          </p>
          {invite.time_limit_minutes ? (
            <p className={styles.timeLimitInfo}>
              {L.timeLimit} {invite.time_limit_minutes} {L.min}
            </p>
          ) : null}
          <input
            className={styles.emailInput}
            type="text"
            placeholder={L.firstName}
            value={firstName}
            onChange={(e) => setFirstName(e.target.value)}
          />
          <input
            className={styles.emailInput}
            type="text"
            placeholder={L.lastName}
            value={lastName}
            onChange={(e) => setLastName(e.target.value)}
          />
          <input
            className={styles.emailInput}
            type="email"
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && void startInterview()}
            disabled={!!invite.candidate_email}
          />
          {errMsg ? <p className={styles.errorText}>{errMsg}</p> : null}
          <div>
            <button
              className={styles.btnPrimary}
              disabled={consuming || !email.trim()}
              onClick={() => void startInterview()}
            >
              {consuming ? L.starting : L.start}
            </button>
          </div>
          <p className={styles.attemptsInfo}>
            {L.attemptsLeft} {invite.attempts_remaining}
          </p>
        </div>
      </div>
    );
  }

  const mode = invite?.interview_mode || "both";
  const showText = mode !== "voice";
  const showVoice = mode !== "text";

  return (
    <div className={styles.wrapper}>
      <div className={styles.header}>
        <div>
          <h1 className={styles.headerTitle}>
            {invite?.position_title || L.interview}
          </h1>
          <span className={styles.headerSub}>{email}</span>
        </div>
        <div className={styles.headerRight}>
          {remainingSeconds !== null ? (
            <div
              className={
                remainingSeconds <= 60
                  ? styles.timerCritical
                  : remainingSeconds <= 300
                    ? styles.timerWarning
                    : styles.timer
              }
            >
            {remainingSeconds <= 0
              ? L.timeUp
              : formatTime(remainingSeconds)}
            </div>
          ) : null}
          <button
            className={styles.btnEnd}
            onClick={() => void endInterview()}
          >
            {L.finish}
          </button>
        </div>
      </div>
      <div className={styles.chatArea}>
        <MessageList
          messages={messages}
          loading={loading}
          LoadingIndicator={LoadingIndicator}
        />
        {showText ? (
          <MessageInput
            inputRef={inputRef}
            input={input}
            loading={loading}
            onChange={setInput}
            onSubmit={sendMessage}
            footerRight={null}
            audioControls={
              showVoice ? (
                <VoiceControls
                  statusMessage={audioChat.statusMessage}
                  recordingError={audioChat.recordingError}
                  permissionError={audioChat.permissionError}
                  isVoiceConnected={audioChat.isVoiceConnected}
                  isVoiceConnecting={audioChat.isVoiceConnecting}
                  onStartVoice={audioChat.startVoiceChat}
                  onStopVoice={audioChat.stopVoiceChat}
                />
              ) : undefined
            }
          />
        ) : (
          <div style={{ padding: 16, textAlign: "center" }}>
            <VoiceControls
              statusMessage={audioChat.statusMessage}
              recordingError={audioChat.recordingError}
              permissionError={audioChat.permissionError}
              isVoiceConnected={audioChat.isVoiceConnected}
              isVoiceConnecting={audioChat.isVoiceConnecting}
              onStartVoice={audioChat.startVoiceChat}
              onStopVoice={audioChat.stopVoiceChat}
            />
          </div>
        )}
      </div>
    </div>
  );
}
