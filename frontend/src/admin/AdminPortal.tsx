import { useState } from "react";
import { KnowledgeAdmin } from "./knowledge/KnowledgeAdmin";
import { OnboardingAdmin } from "./onboarding/OnboardingAdmin";
import styles from "./AdminPortal.module.css";

type AdminTab = "chatbot" | "knowledge" | "onboarding";

function ChatbotTab() {
  const [unresolved, setUnresolved] = useState<number | null>(null);

  return (
    <section style={{ padding: 24 }}>
      <h2>Chatbot Dashboard</h2>
      <p style={{ opacity: 0.6, marginTop: 0 }}>
        Мониторинг чата: нераспознанные вопросы, метрики качества, логи сессий.
      </p>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 16, marginTop: 24 }}>
        <div style={{ background: "rgba(255,255,255,.06)", borderRadius: 12, padding: 20 }}>
          <div style={{ fontSize: 32, fontWeight: 800, color: "#38bdf8" }}>—</div>
          <div style={{ fontSize: 13, opacity: 0.6, marginTop: 4 }}>Открытых вопросов</div>
        </div>
        <div style={{ background: "rgba(255,255,255,.06)", borderRadius: 12, padding: 20 }}>
          <div style={{ fontSize: 32, fontWeight: 800, color: "#22c55e" }}>—</div>
          <div style={{ fontSize: 13, opacity: 0.6, marginTop: 4 }}>Ответов сегодня</div>
        </div>
        <div style={{ background: "rgba(255,255,255,.06)", borderRadius: 12, padding: 20 }}>
          <div style={{ fontSize: 32, fontWeight: 800, color: "#f59e0b" }}>—</div>
          <div style={{ fontSize: 13, opacity: 0.6, marginTop: 4 }}>Эскалаций</div>
        </div>
      </div>
      <p style={{ marginTop: 32, opacity: 0.4, fontSize: 13 }}>
        Полная аналитика доступна в Phase 5.
      </p>
    </section>
  );
}

export function AdminPortal() {
  const [tab, setTab] = useState<AdminTab>("knowledge");

  const tabs: { id: AdminTab; label: string }[] = [
    { id: "knowledge", label: "База знаний" },
    { id: "onboarding", label: "Онбординг" },
    { id: "chatbot", label: "Chatbot" },
  ];

  return (
    <div className={styles.portal}>
      <header className={styles.header}>
        <h2 className={styles.title}>WinLab Admin</h2>
        <nav className={styles.tabs}>
          {tabs.map(t => (
            <button
              key={t.id}
              className={`${styles.tab} ${tab === t.id ? styles.tabActive : ""}`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>

      <main className={styles.content}>
        {tab === "knowledge" && <KnowledgeAdmin />}
        {tab === "onboarding" && <OnboardingAdmin />}
        {tab === "chatbot" && <ChatbotTab />}
      </main>
    </div>
  );
}
