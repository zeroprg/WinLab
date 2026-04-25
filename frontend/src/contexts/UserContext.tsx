import { createContext, useContext, useState, useCallback, type ReactNode } from "react";
import { apiUrl } from "../services/api";

export type UserRole = "candidate" | "admin" | "superadmin";

interface UserContextValue {
  userId: string;
  displayName: string;
  token: string;
  role: UserRole;
  setDisplayName: (name: string) => void;
  login: (email: string) => void;
  loginAdmin: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const UserContext = createContext<UserContextValue>({
  userId: "",
  displayName: "",
  token: "",
  role: "candidate",
  setDisplayName: () => {},
  login: () => {},
  loginAdmin: async () => {},
  logout: () => {},
});

const STORAGE_KEY_USER_ID = "chat_user_id";
const STORAGE_KEY_DISPLAY = "chat_display_name";
const STORAGE_KEY_TOKEN = "chat_auth_token";
const STORAGE_KEY_ROLE = "chat_user_role";

function getSavedUserId(): string {
  return localStorage.getItem(STORAGE_KEY_USER_ID) || "";
}

export function UserProvider({ children }: { children: ReactNode }) {
  const [userId, setUserId] = useState(getSavedUserId);
  const [displayName, setDisplayNameState] = useState(
    () => localStorage.getItem(STORAGE_KEY_DISPLAY) || "",
  );
  const [token, setToken] = useState(
    () => localStorage.getItem(STORAGE_KEY_TOKEN) || "",
  );
  const [role, setRole] = useState<UserRole>(
    () => (localStorage.getItem(STORAGE_KEY_ROLE) as UserRole) || "candidate",
  );

  const setDisplayName = useCallback(
    (name: string) => {
      const trimmed = name.trim();
      setDisplayNameState(trimmed);
      localStorage.setItem(STORAGE_KEY_DISPLAY, trimmed);

      if (userId) {
        fetch(apiUrl(`/api/user/${encodeURIComponent(userId)}`), {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ display_name: trimmed }),
        }).catch(() => {});
      }
    },
    [userId],
  );

  const login = useCallback((email: string) => {
    const id = email.trim().toLowerCase();
    setUserId(id);
    localStorage.setItem(STORAGE_KEY_USER_ID, id);
    setDisplayNameState(id);
    localStorage.setItem(STORAGE_KEY_DISPLAY, id);
    setToken("");
    localStorage.removeItem(STORAGE_KEY_TOKEN);
    setRole("candidate");
    localStorage.setItem(STORAGE_KEY_ROLE, "candidate");

    fetch(apiUrl(`/api/user/${encodeURIComponent(id)}`), {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ display_name: id }),
    }).catch(() => {});
  }, []);

  const loginAdmin = useCallback(async (email: string, password: string) => {
    const res = await fetch(apiUrl("/api/auth/login"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Login failed" }));
      throw new Error(err.detail || "Login failed");
    }

    const data = await res.json();
    const jwt = data.token as string;
    const userRole = data.role as UserRole;
    const id = data.user_id as string;
    const name = (data.display_name as string) || id;

    setUserId(id);
    localStorage.setItem(STORAGE_KEY_USER_ID, id);
    setDisplayNameState(name);
    localStorage.setItem(STORAGE_KEY_DISPLAY, name);
    setToken(jwt);
    localStorage.setItem(STORAGE_KEY_TOKEN, jwt);
    setRole(userRole);
    localStorage.setItem(STORAGE_KEY_ROLE, userRole);
  }, []);

  const logout = useCallback(() => {
    setUserId("");
    setDisplayNameState("");
    setToken("");
    setRole("candidate");
    localStorage.removeItem(STORAGE_KEY_USER_ID);
    localStorage.removeItem(STORAGE_KEY_DISPLAY);
    localStorage.removeItem(STORAGE_KEY_TOKEN);
    localStorage.removeItem(STORAGE_KEY_ROLE);
  }, []);

  return (
    <UserContext.Provider
      value={{ userId, displayName, token, role, setDisplayName, login, loginAdmin, logout }}
    >
      {children}
    </UserContext.Provider>
  );
}

export function useUserId(): string {
  return useContext(UserContext).userId;
}

export function useUser(): UserContextValue {
  return useContext(UserContext);
}

export default UserContext;
