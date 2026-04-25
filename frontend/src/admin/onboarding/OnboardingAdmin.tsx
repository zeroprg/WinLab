import { useCallback, useEffect, useState } from "react";
import { apiUrl, authFetch } from "../../shared/api/api";

interface OnboardingTask {
  id: string;
  plan_id: string;
  title: string;
  description?: string | null;
  owner_id?: string | null;
  due_date?: string | null;
  status: string;
  completed_at?: string | null;
}

interface OnboardingPlan {
  id: string;
  employee_id: string;
  title: string;
  stage: string;
  status: string;
  tasks: OnboardingTask[];
}

const STAGES = ["day1", "week1", "month1"];
const TASK_STATUSES = ["pending", "in_progress", "done"];

export function OnboardingAdmin() {
  const [plans, setPlans] = useState<OnboardingPlan[]>([]);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);

  const [newEmpId, setNewEmpId] = useState("");
  const [newTitle, setNewTitle] = useState("Адаптация");
  const [newStage, setNewStage] = useState("day1");

  const [newTaskTitle, setNewTaskTitle] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    const r = await authFetch(apiUrl("/api/onboarding"));
    if (r.ok) setPlans((await r.json()) as OnboardingPlan[]);
    else setErr(`Load: HTTP ${r.status}`);
  }, []);

  useEffect(() => { void load(); }, [load]);

  const createPlan = async () => {
    if (!newEmpId.trim()) { setErr("Введите email сотрудника."); return; }
    const r = await authFetch(apiUrl("/api/onboarding"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ employee_id: newEmpId.trim(), title: newTitle, stage: newStage }),
    });
    if (r.ok) {
      setMsg("План создан."); setNewEmpId(""); setNewTitle("Адаптация"); setNewStage("day1");
      await load();
    } else setErr(`Create: HTTP ${r.status}`);
  };

  const updatePlanStatus = async (plan: OnboardingPlan, status: string) => {
    const r = await authFetch(apiUrl(`/api/onboarding/${plan.id}`), {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
    if (r.ok) { setMsg("Обновлено."); await load(); }
    else setErr(`Update: HTTP ${r.status}`);
  };

  const addTask = async (plan_id: string) => {
    const title = newTaskTitle[plan_id] || "";
    if (!title.trim()) return;
    const r = await authFetch(apiUrl(`/api/onboarding/${plan_id}/tasks`), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: title.trim() }),
    });
    if (r.ok) {
      setMsg("Задача добавлена.");
      setNewTaskTitle(m => ({ ...m, [plan_id]: "" }));
      await load();
    } else setErr(`AddTask: HTTP ${r.status}`);
  };

  const updateTaskStatus = async (task: OnboardingTask, status: string) => {
    const r = await authFetch(apiUrl(`/api/onboarding/tasks/${task.id}`), {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
    if (r.ok) { await load(); }
    else setErr(`TaskStatus: HTTP ${r.status}`);
  };

  const done = (plan: OnboardingPlan) => plan.tasks.filter(t => t.status === "done").length;

  return (
    <section style={{ padding: 24 }}>
      <h2>Онбординг</h2>
      {err && <p style={{ color: "red" }}>{err}</p>}
      {msg && <p style={{ color: "green" }}>{msg}</p>}

      <div style={{ display: "grid", gap: 8, marginBottom: 24, maxWidth: 500 }}>
        <h3>Создать план адаптации</h3>
        <input placeholder="Email сотрудника" value={newEmpId} onChange={e => setNewEmpId(e.target.value)} style={{ padding: 8, borderRadius: 6, border: "1px solid #555" }} />
        <input placeholder="Название плана" value={newTitle} onChange={e => setNewTitle(e.target.value)} style={{ padding: 8, borderRadius: 6, border: "1px solid #555" }} />
        <div style={{ display: "flex", gap: 8 }}>
          <select value={newStage} onChange={e => setNewStage(e.target.value)}>
            {STAGES.map(s => <option key={s} value={s}>{s === "day1" ? "1 день" : s === "week1" ? "1 неделя" : "1 месяц"}</option>)}
          </select>
          <button onClick={createPlan} style={{ padding: "8px 16px", background: "#2563eb", color: "#fff", border: "none", borderRadius: 6 }}>Создать</button>
        </div>
      </div>

      {plans.map(plan => (
        <div key={plan.id} style={{ border: "1px solid #333", borderRadius: 10, marginBottom: 16, overflow: "hidden" }}>
          <div
            style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 16px", cursor: "pointer", background: "#1e293b" }}
            onClick={() => setExpanded(expanded === plan.id ? null : plan.id)}
          >
            <div>
              <strong>{plan.title}</strong>
              <span style={{ marginLeft: 12, opacity: 0.6, fontSize: 13 }}>
                {plan.employee_id} · {plan.stage} · {done(plan)}/{plan.tasks.length} задач
              </span>
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <select
                value={plan.status}
                onChange={e => { e.stopPropagation(); updatePlanStatus(plan, e.target.value); }}
                onClick={e => e.stopPropagation()}
                style={{ fontSize: 12 }}
              >
                {["active", "completed", "paused"].map(s => <option key={s} value={s}>{s}</option>)}
              </select>
              <span>{expanded === plan.id ? "▲" : "▼"}</span>
            </div>
          </div>

          {expanded === plan.id && (
            <div style={{ padding: 16 }}>
              {plan.tasks.length === 0 && <p style={{ opacity: 0.5 }}>Задачи не добавлены.</p>}
              {plan.tasks.map(task => (
                <div key={task.id} style={{ display: "flex", alignItems: "center", gap: 12, padding: "6px 0", borderBottom: "1px solid #222" }}>
                  <span style={{ flex: 1 }}>{task.title}</span>
                  <select
                    value={task.status}
                    onChange={e => updateTaskStatus(task, e.target.value)}
                    style={{ fontSize: 12 }}
                  >
                    {TASK_STATUSES.map(s => <option key={s} value={s}>{s === "pending" ? "⏳ ожидает" : s === "in_progress" ? "🔄 в работе" : "✅ готово"}</option>)}
                  </select>
                </div>
              ))}
              <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                <input
                  placeholder="Новая задача…"
                  value={newTaskTitle[plan.id] || ""}
                  onChange={e => setNewTaskTitle(m => ({ ...m, [plan.id]: e.target.value }))}
                  onKeyDown={e => { if (e.key === "Enter") addTask(plan.id); }}
                  style={{ flex: 1, padding: 6, borderRadius: 6, border: "1px solid #555" }}
                />
                <button onClick={() => addTask(plan.id)} style={{ padding: "6px 12px", background: "#22c55e", color: "#fff", border: "none", borderRadius: 6 }}>+ Задача</button>
              </div>
            </div>
          )}
        </div>
      ))}
      {plans.length === 0 && <p style={{ opacity: 0.5 }}>Планы не найдены.</p>}
    </section>
  );
}
