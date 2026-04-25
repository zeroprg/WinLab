import type { Message } from "../../types/chat";
import { OnboardingCard } from "./cards/OnboardingCard";
import { KBResultCard } from "./cards/KBResultCard";
import { QuickReplies } from "./cards/QuickReplies";
import styles from "./ChatMessage.module.css";

type Props = {
  msg: Message;
  onQuickReply?: (choice: string) => void;
};

export default function ChatMessage({ msg, onQuickReply }: Props) {
  const isUser = msg.role === "user";
  const bubble = isUser ? styles.user : styles.bot;

  if (isUser || !msg.card_type || msg.card_type === "text") {
    return (
      <div className={styles.line}>
        <div className={bubble} style={{ whiteSpace: "pre-wrap" }}>{msg.content}</div>
      </div>
    );
  }

  const meta = msg.metadata ?? {};

  return (
    <div className={styles.line}>
      <div className={bubble}>
        {msg.card_type === "onboarding_plan" && (
          <OnboardingCard content={msg.content} metadata={meta} onQuickReply={onQuickReply} />
        )}
        {msg.card_type === "kb_result" && (
          <KBResultCard content={msg.content} metadata={meta} />
        )}
        {msg.card_type === "quick_replies" && (
          <QuickReplies content={msg.content} metadata={meta} onQuickReply={onQuickReply} />
        )}
      </div>
    </div>
  );
}
