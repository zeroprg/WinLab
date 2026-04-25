import { useEffect, useRef, useState } from "react";
import ChatHeader from "./components/chat/ChatHeader";
import MessageList from "./components/chat/MessageList";
import MessageInput from "./components/chat/MessageInput";
import LoadingIndicator from "./components/chat/LoadingIndicator";
import VoiceControls from "./components/chat/VoiceControls";
import UserLoginOverlay from "./components/chat/UserLoginOverlay";
import styles from "./Chatbot.module.css";

import {
  TEST_FETCH,
  getChatStatusRight,
} from "./services/api";
import useAudioChat from "./hooks/useAudioChat";
import useChat from "./hooks/useChat";
import { useUser } from "./contexts/UserContext";

export default function Chatbot() {
  const [isOpen, setIsOpen] = useState(false);
  const [fabHover, setFabHover] = useState(false);
  const { userId, login, loginAdmin } = useUser();

  const {
    messages,
    input,
    setInput,
    loading,
    sendMessage,
    addMessage,
    appendToMessage,
    insertBeforeMessage,
    setMessageContent,
  } = useChat();
  const audioChat = useAudioChat(addMessage, appendToMessage, insertBeforeMessage, setMessageContent);

  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [isOpen]);

  const statusRight = getChatStatusRight();

  return (
    <>
      {/* FAB */}
      <button
        aria-label={isOpen ? "Close chat" : "Open chat"}
        className={`${styles.fab} ${fabHover ? styles.fabHover : ""}`}
        onMouseEnter={() => setFabHover(true)}
        onMouseLeave={() => setFabHover(false)}
        onClick={() => setIsOpen((v) => !v)}
        title={isOpen ? "Close chat" : "Chat with us"}
      >
        {isOpen ? (
          <svg
            width="26"
            height="26"
            viewBox="0 0 24 24"
            fill="none"
            style={{ display: "block" }}
          >
            <path
              d="M6 6l12 12M18 6L6 18"
              stroke="white"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
        ) : (
          <svg
            width="26"
            height="26"
            viewBox="0 0 24 24"
            fill="none"
            style={{ display: "block" }}
          >
            <path
              d="M4 6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H9l-4 3v-3H6a2 2 0 0 1-2-2V6z"
              stroke="white"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        )}
      </button>

      {/* Panel */}
      <section
        className={`${styles.panel} ${
          isOpen ? styles.panelOpen : styles.panelClosed
        }`}
        aria-hidden={!isOpen}
      >
        <ChatHeader onClose={() => setIsOpen(false)} />
        {!userId && <UserLoginOverlay onSubmit={login} onAdminLogin={loginAdmin} />}
        <MessageList
          messages={messages}
          loading={loading}
          LoadingIndicator={LoadingIndicator}
        />
        <MessageInput
          inputRef={inputRef}
          input={input}
          loading={loading}
          onChange={setInput}
          onSubmit={sendMessage}
          footerRight={
            <>
              Mode: {TEST_FETCH ? "TEST_FETCH" : "REAL_API"} {statusRight}
            </>
          }
          audioControls={
            <VoiceControls
              statusMessage={audioChat.statusMessage}
              recordingError={audioChat.recordingError}
              permissionError={audioChat.permissionError}
              isVoiceConnected={audioChat.isVoiceConnected}
              isVoiceConnecting={audioChat.isVoiceConnecting}
              onStartVoice={audioChat.startVoiceChat}
              onStopVoice={audioChat.stopVoiceChat}
            />
          }
        />
      </section>
    </>
  );
}
