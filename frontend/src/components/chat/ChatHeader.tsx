import { useUser } from "../../contexts/UserContext";
import styles from "./ChatHeader.module.css";

type Props = { title?: string; onClose(): void };

export default function ChatHeader({ title = "AI Assistant", onClose }: Props) {
  const { displayName } = useUser();

  return (
    <header className={styles.header}>
      <div className={styles.title}>
        {title}
        {displayName && (
          <span style={{ fontSize: "0.75em", opacity: 0.7, marginLeft: 8 }}>
            ({displayName})
          </span>
        )}
      </div>
      <button className={styles.closeBtn} onClick={onClose} aria-label="Close">×</button>
    </header>
  );
}
