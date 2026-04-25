import type { MessageMetadata } from "../../../types/chat";
import styles from "./Cards.module.css";

type Props = {
  content: string;
  metadata: MessageMetadata;
  onQuickReply?: (choice: string) => void;
};

export function QuickReplies({ content, metadata, onQuickReply }: Props) {
  const choices = metadata.choices ?? [];

  return (
    <div className={styles.card}>
      <p className={styles.cardText}>{content}</p>
      {choices.length > 0 && (
        <div className={styles.quickReplies}>
          {choices.map(choice => (
            <button
              key={choice}
              className={styles.quickReplyBtn}
              onClick={() => onQuickReply?.(choice)}
            >
              {choice}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
