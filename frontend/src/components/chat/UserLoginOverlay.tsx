import { useState, useRef, useEffect } from "react";
import { useLocale } from "../../contexts/LocaleContext";
import type { AppLocale } from "../../i18n/translations";
import { apiUrl } from "../../services/api";
import styles from "./UserLoginOverlay.module.css";

type Props = {
  onSubmit: (email: string) => void;
  onAdminLogin: (email: string, password: string) => Promise<void>;
};

export default function UserLoginOverlay({ onSubmit, onAdminLogin }: Props) {
  const { locale, setLocale, t } = useLocale();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [avatarBroken, setAvatarBroken] = useState(false);
  const [needsPassword, setNeedsPassword] = useState(false);
  const [checking, setChecking] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    if (needsPassword) passwordRef.current?.focus();
  }, [needsPassword]);

  const handleEmailSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = email.trim();
    if (!trimmed) {
      setError(t("loginErrorEmpty"));
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed)) {
      setError(t("loginErrorInvalid"));
      return;
    }
    setError("");
    setChecking(true);

    try {
      const res = await fetch(apiUrl("/api/auth/check"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: trimmed }),
      });
      const data = await res.json();
      if (data.is_admin) {
        setNeedsPassword(true);
        setChecking(false);
        return;
      }
      const errMsg = locale === "en"
        ? "Admin access only. Candidates must use the interview link provided by the recruiter."
        : "Вход только для администраторов. Кандидатам необходимо использовать ссылку на интервью, полученную от рекрутера.";
      setError(errMsg);
      setChecking(false);
      return;
    } catch {
      const errMsg = locale === "en"
        ? "Connection error. Please try again."
        : "Ошибка соединения. Попробуйте ещё раз.";
      setError(errMsg);
    }

    setChecking(false);
  };

  const handlePasswordSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!password) {
      setError(t("loginPasswordError"));
      return;
    }
    setError("");
    setChecking(true);
    try {
      await onAdminLogin(email.trim(), password);
    } catch (err: any) {
      setError(err.message || t("loginPasswordError"));
      setChecking(false);
    }
  };

  const handleBackToEmail = () => {
    setNeedsPassword(false);
    setPassword("");
    setError("");
  };

  return (
    <div className={styles.overlay}>
      <div className={styles.card}>
        <div className={styles.langRow}>
          <label htmlFor="login-locale" className={styles.langLabel}>
            {t("loginLanguageLabel")}
          </label>
          <select
            id="login-locale"
            className={styles.select}
            value={locale}
            onChange={(e) => setLocale(e.target.value as AppLocale)}
            aria-label={t("loginLanguageLabel")}
          >
            <option value="ru">Русский</option>
            <option value="en">English</option>
          </select>
        </div>
        <div className={styles.icon}>
          {!avatarBroken ? (
            <img
              src={apiUrl("/api/branding/avatar")}
              alt=""
              className={styles.avatarImg}
              width={72}
              height={72}
              onError={() => setAvatarBroken(true)}
            />
          ) : (
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path
                d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <circle
                cx="12"
                cy="7"
                r="4"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          )}
        </div>
        <h2 className={styles.heading}>{t("loginHeading")}</h2>
        <p className={styles.subtitle}>{t("loginSubtitle")}</p>

        {!needsPassword ? (
          <form onSubmit={handleEmailSubmit} className={styles.form}>
            <input
              ref={inputRef}
              type="email"
              className={styles.input}
              placeholder={t("loginPlaceholder")}
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                if (error) setError("");
              }}
              autoComplete="email"
              disabled={checking}
            />
            {error && <div className={styles.error}>{error}</div>}
            <button type="submit" className={styles.button} disabled={checking}>
              {checking ? "..." : t("loginContinue")}
            </button>
          </form>
        ) : (
          <form onSubmit={handlePasswordSubmit} className={styles.form}>
            <div className={styles.emailDisplay}>{email}</div>
            <label className={styles.passwordLabel}>{t("loginPasswordLabel")}</label>
            <input
              ref={passwordRef}
              type="password"
              className={styles.input}
              placeholder={t("loginPasswordPlaceholder")}
              value={password}
              onChange={(e) => {
                setPassword(e.target.value);
                if (error) setError("");
              }}
              autoComplete="current-password"
              disabled={checking}
            />
            {error && <div className={styles.error}>{error}</div>}
            <button type="submit" className={styles.button} disabled={checking}>
              {checking ? "..." : t("loginSignIn")}
            </button>
            <button
              type="button"
              className={styles.backButton}
              onClick={handleBackToEmail}
              disabled={checking}
            >
              {t("loginBackToEmail")}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
