import type { KBSource, MessageMetadata } from "../../../types/chat";
import styles from "./Cards.module.css";

type Props = {
  content: string;
  metadata: MessageMetadata;
};

function SourceChip({ source }: { source: KBSource }) {
  return source.source_url ? (
    <a href={source.source_url} target="_blank" rel="noopener noreferrer" className={styles.sourceChip}>
      {source.title}
    </a>
  ) : (
    <span className={styles.sourceChip}>{source.title}</span>
  );
}

export function KBResultCard({ content, metadata }: Props) {
  const sources = metadata.sources ?? [];

  return (
    <div className={styles.card}>
      <p className={styles.cardText}>{content}</p>
      {sources.length > 0 && (
        <div className={styles.sources}>
          <span className={styles.sourcesLabel}>Источники:</span>
          {sources.map(s => <SourceChip key={s.document_id} source={s} />)}
        </div>
      )}
    </div>
  );
}
