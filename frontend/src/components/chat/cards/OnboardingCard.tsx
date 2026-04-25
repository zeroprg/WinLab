import type { MessageMetadata, OnboardingTask } from "../../../types/chat";
import styles from "./Cards.module.css";

type Props = {
  content: string;
  metadata: MessageMetadata;
  onQuickReply?: (choice: string) => void;
};

function TaskRow({ task }: { task: OnboardingTask }) {
  const icon = task.status === "done" ? "✅" : task.status === "in_progress" ? "🔄" : "⏳";
  return (
    <div className={styles.taskRow}>
      <span className={styles.taskIcon}>{icon}</span>
      <span className={task.status === "done" ? styles.taskDone : undefined}>{task.title}</span>
    </div>
  );
}

export function OnboardingCard({ content, metadata, onQuickReply }: Props) {
  const { progress = 0, done = 0, total = 0, tasks = [], quick_replies = [] } = metadata;

  return (
    <div className={styles.card}>
      <p className={styles.cardText}>{content}</p>

      {total > 0 && (
        <div className={styles.progressBar}>
          <div className={styles.progressFill} style={{ width: `${progress}%` }} />
        </div>
      )}

      {tasks.length > 0 && (
        <div className={styles.taskList}>
          {tasks.slice(0, 5).map(t => <TaskRow key={t.id} task={t} />)}
          {tasks.length > 5 && (
            <p className={styles.taskMore}>ещё {tasks.length - 5} задач…</p>
          )}
        </div>
      )}

      {quick_replies.length > 0 && (
        <div className={styles.quickReplies}>
          {quick_replies.map(choice => (
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
