import { useLocale } from "../../contexts/LocaleContext";
import styles from "./VoiceControls.module.css";

type Props = {
  statusMessage: string;
  recordingError?: string;
  permissionError?: string;
  isVoiceConnected: boolean;
  isVoiceConnecting: boolean;
  onStartVoice: () => Promise<void>;
  onStopVoice: () => void;
};

export default function VoiceControls({
  statusMessage,
  recordingError,
  permissionError,
  isVoiceConnected,
  isVoiceConnecting,
  onStartVoice,
  onStopVoice,
}: Props) {
  const { t } = useLocale();
  return (
    <div className={styles.container}>
      <div className={styles.buttons}>
        <button
          type="button"
          data-testid="voice-chat-toggle"
          className={`${styles.voiceButton} ${isVoiceConnected ? styles.voiceActive : ""}`}
          onClick={() => (isVoiceConnected ? onStopVoice() : onStartVoice())}
          disabled={isVoiceConnecting}
        >
          {isVoiceConnecting
            ? t("voiceBtnConnecting")
            : isVoiceConnected
              ? t("voiceBtnEnd")
              : t("voiceBtnStart")}
        </button>
      </div>
      <div className={styles.status}>
        <span>{statusMessage}</span>
      </div>
      {permissionError && <div className={styles.error}>{permissionError}</div>}
      {recordingError && <div className={styles.error}>{recordingError}</div>}
    </div>
  );
}
