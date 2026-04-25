import { useEffect, useState } from "react";
import Chatbot from "./Chatbot";
import ErrorBoundary from "./components/ErrorBoundary";
import UserLoginOverlay from "./components/chat/UserLoginOverlay";
import InterviewPage from "./pages/InterviewPage";
import { LocaleProvider, useLocale } from "./contexts/LocaleContext";
import { UserProvider, useUser } from "./contexts/UserContext";
import appStyles from "./App.module.css";

function useHashRoute(): { path: string; param: string } {
  const parse = () => {
    const hash = window.location.hash.replace(/^#\/?/, "");
    const [first, ...rest] = hash.split("/");
    return { path: first || "", param: rest.join("/") };
  };
  const [route, setRoute] = useState(parse);
  useEffect(() => {
    const handler = () => setRoute(parse());
    window.addEventListener("hashchange", handler);
    return () => window.removeEventListener("hashchange", handler);
  }, []);
  return route;
}

function MainContent() {
  const { role, userId, login, loginAdmin, logout } = useUser();
  const { t } = useLocale();
  const isAdmin = role === "admin" || role === "superadmin";

  if (!userId) {
    return (
      <div className={appStyles.page}>
        <ErrorBoundary>
          <UserLoginOverlay onSubmit={login} onAdminLogin={loginAdmin} />
        </ErrorBoundary>
      </div>
    );
  }

  return (
    <div className={appStyles.page}>
      <header className={appStyles.hero}>
        <h1 className={appStyles.heroTitle}>WinLab HR Assistant</h1>
        {userId && (
          <button className={appStyles.logoutBtn} onClick={logout}>
            {isAdmin ? (role === "superadmin" ? "SA" : "A") + ": " : ""}
            {userId} — {t("logoutButton")}
          </button>
        )}
      </header>
      <ErrorBoundary>
        <Chatbot />
      </ErrorBoundary>
    </div>
  );
}

export default function App() {
  const { path, param } = useHashRoute();

  if (path === "interview" && param) {
    return (
      <LocaleProvider>
        <UserProvider>
          <ErrorBoundary>
            <InterviewPage token={param} />
          </ErrorBoundary>
        </UserProvider>
      </LocaleProvider>
    );
  }

  return (
    <LocaleProvider>
      <UserProvider>
        <MainContent />
      </UserProvider>
    </LocaleProvider>
  );
}
