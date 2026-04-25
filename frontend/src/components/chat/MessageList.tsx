import React, { useEffect, useRef } from "react";
import type { Message } from "../../types/chat";
import ChatMessage from "./ChatMessage";
import styles from "./MessageList.module.css";

type Props = {
  messages: Message[];
  loading?: boolean;
  LoadingIndicator?: React.ComponentType;
};

export default function MessageList({ messages, loading, LoadingIndicator }: Props) {
  const endRef = useRef<HTMLDivElement | null>(null);
  const listRef = useRef<HTMLDivElement | null>(null);
  const userIsScrolling = useRef(false);

  useEffect(() => {
    // Only auto-scroll if user is not manually scrolling
    if (!userIsScrolling.current && endRef.current) {
      endRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, loading]);

  const handleWheel = () => {
    userIsScrolling.current = true;
    const timer = setTimeout(() => {
      userIsScrolling.current = false;
    }, 1000);
    return () => clearTimeout(timer);
  };

  return (
    <div className={styles.box} ref={listRef} onWheel={handleWheel}>
      {messages.map((m) => (
        <ChatMessage key={m.id} msg={m} />
      ))}
      {loading && LoadingIndicator ? <LoadingIndicator /> : null}
      <div ref={endRef} />
    </div>
  );
}
