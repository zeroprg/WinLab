import { useCallback, useEffect, useRef, useState } from "react";
import { apiUrl, authFetch } from "../../shared/api/api";

interface KnowledgeDoc {
  id: string;
  title: string;
  status: string;
  locale: string;
  content_preview: string;
  source_url?: string | null;
  created_at?: string | null;
}

interface UnresolvedQuery {
  id: string;
  user_id?: string | null;
  question: string;
  status: string;
  answer?: string | null;
  created_at?: string | null;
}

const STATUSES = ["draft", "published", "archived"];

export function KnowledgeAdmin() {
  const [docs, setDocs] = useState<KnowledgeDoc[]>([]);
  const [unresolved, setUnresolved] = useState<UnresolvedQuery[]>([]);
  const [tab, setTab] = useState<"kb" | "unresolved">("kb");
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");

  const [newTitle, setNewTitle] = useState("");
  const [newContent, setNewContent] = useState("");
  const [newLocale, setNewLocale] = useState("ru");
  const [newStatus, setNewStatus] = useState("draft");

  const [answerMap, setAnswerMap] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    const r = await authFetch(apiUrl("/api/knowledge"));
    if (r.ok) setDocs((await r.json()) as KnowledgeDoc[]);
    else setErr(`KB load: HTTP ${r.status}`);
  }, []);

  const loadUnresolved = useCallback(async () => {
    const r = await authFetch(apiUrl("/api/knowledge/unresolved?status=open"));
    if (r.ok) setUnresolved((await r.json()) as UnresolvedQuery[]);
  }, []);

  useEffect(() => { void load(); void loadUnresolved(); }, [load, loadUnresolved]);

  const createDoc = async () => {
    if (!newTitle.trim()) return;
    const r = await authFetch(apiUrl("/api/knowledge"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: newTitle.trim(), content: newContent.trim(), locale: newLocale, status: newStatus }),
    });
    if (r.ok) {
      setMsg("Документ создан.");
      setNewTitle(""); setNewContent(""); setNewLocale("ru"); setNewStatus("draft");
      await load();
    } else { setErr(`Create: HTTP ${r.status}`); }
  };

  const changeStatus = async (doc: KnowledgeDoc, status: string) => {
    const r = await authFetch(apiUrl(`/api/knowledge/${doc.id}`), {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
    if (r.ok) { setMsg(`Статус обновлён.`); await load(); }
    else setErr(`Update: HTTP ${r.status}`);
  };

  const deleteDoc = async (id: string) => {
    if (!confirm("Удалить документ?")) return;
    const r = await authFetch(apiUrl(`/api/knowledge/${id}`), { method: "DELETE" });
    if (r.ok || r.status === 204) { setMsg("Документ удалён."); await load(); }
    else setErr(`Delete: HTTP ${r.status}`);
  };

  const resolveQuery = async (id: string) => {
    const answer = answerMap[id] || "";
    const r = await authFetch(apiUrl(`/api/knowledge/unresolved/${id}`), {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: "resolved", answer }),
    });
    if (r.ok) { setMsg("Вопрос закрыт."); await loadUnresolved(); }
    else setErr(`Resolve: HTTP ${r.status}`);
  };

  return (
    <section style={{ padding: 24 }}>
      <h2>База знаний</h2>
      {err && <p style={{ color: "red" }}>{err}</p>}
      {msg && <p style={{ color: "green" }}>{msg}</p>}

      <div style={{ display: "flex", gap: 12, marginBottom: 16 }}>
        <button onClick={() => setTab("kb")} style={{ fontWeight: tab === "kb" ? "bold" : "normal" }}>Документы</button>
        <button onClick={() => setTab("unresolved")} style={{ fontWeight: tab === "unresolved" ? "bold" : "normal" }}>
          Нераспознанные вопросы {unresolved.length > 0 ? `(${unresolved.length})` : ""}
        </button>
      </div>

      {tab === "kb" && (
        <>
          <div style={{ display: "grid", gap: 8, marginBottom: 24, maxWidth: 600 }}>
            <h3>Добавить документ</h3>
            <input placeholder="Заголовок" value={newTitle} onChange={e => setNewTitle(e.target.value)} style={{ padding: 8, borderRadius: 6, border: "1px solid #555" }} />
            <textarea rows={5} placeholder="Текст документа (будет разбит на чанки)" value={newContent} onChange={e => setNewContent(e.target.value)} style={{ padding: 8, borderRadius: 6, border: "1px solid #555" }} />
            <div style={{ display: "flex", gap: 8 }}>
              <select value={newLocale} onChange={e => setNewLocale(e.target.value)}>
                <option value="ru">Русский</option><option value="en">English</option>
              </select>
              <select value={newStatus} onChange={e => setNewStatus(e.target.value)}>
                {STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
              <button onClick={createDoc} style={{ padding: "8px 16px", background: "#2563eb", color: "#fff", border: "none", borderRadius: 6 }}>Создать</button>
            </div>
          </div>

          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ textAlign: "left", borderBottom: "1px solid #333" }}>
                <th style={{ padding: 8 }}>Заголовок</th>
                <th style={{ padding: 8 }}>Статус</th>
                <th style={{ padding: 8 }}>Язык</th>
                <th style={{ padding: 8 }}>Превью</th>
                <th style={{ padding: 8 }}></th>
              </tr>
            </thead>
            <tbody>
              {docs.map(doc => (
                <tr key={doc.id} style={{ borderBottom: "1px solid #222" }}>
                  <td style={{ padding: 8 }}>{doc.title}</td>
                  <td style={{ padding: 8 }}>
                    <select value={doc.status} onChange={e => changeStatus(doc, e.target.value)}>
                      {STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </td>
                  <td style={{ padding: 8 }}>{doc.locale}</td>
                  <td style={{ padding: 8, maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {doc.content_preview}
                  </td>
                  <td style={{ padding: 8 }}>
                    <button onClick={() => deleteDoc(doc.id)} style={{ color: "red", background: "none", border: "none", cursor: "pointer" }}>✕</button>
                  </td>
                </tr>
              ))}
              {docs.length === 0 && <tr><td colSpan={5} style={{ padding: 16, textAlign: "center", opacity: 0.5 }}>Документы не найдены</td></tr>}
            </tbody>
          </table>
        </>
      )}

      {tab === "unresolved" && (
        <div>
          {unresolved.length === 0 && <p style={{ opacity: 0.5 }}>Нет открытых вопросов.</p>}
          {unresolved.map(q => (
            <div key={q.id} style={{ border: "1px solid #333", borderRadius: 8, padding: 16, marginBottom: 12 }}>
              <p><strong>Вопрос:</strong> {q.question}</p>
              {q.user_id && <p style={{ fontSize: 12, opacity: 0.7 }}>От: {q.user_id}</p>}
              <textarea
                rows={3}
                placeholder="Ответ HR-администратора…"
                value={answerMap[q.id] || ""}
                onChange={e => setAnswerMap(m => ({ ...m, [q.id]: e.target.value }))}
                style={{ width: "100%", padding: 8, borderRadius: 6, border: "1px solid #555", marginTop: 8 }}
              />
              <button
                onClick={() => resolveQuery(q.id)}
                style={{ marginTop: 8, padding: "6px 14px", background: "#22c55e", color: "#fff", border: "none", borderRadius: 6 }}
              >
                Закрыть вопрос
              </button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
