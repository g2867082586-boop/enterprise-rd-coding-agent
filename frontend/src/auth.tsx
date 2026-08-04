import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { authApi } from "./api";
import type { User } from "./types";

interface AuthState { user: User | null; loading: boolean; refresh: () => Promise<void>; setUser: (user: User | null) => void }
const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const requestVersion = useRef(0);
  const refresh = async () => {
    const version = ++requestVersion.current;
    try { const current = await authApi.me(); if (version === requestVersion.current) setUser(current); }
    catch { if (version === requestVersion.current) setUser(null); }
    finally { if (version === requestVersion.current) setLoading(false); }
  };
  useEffect(() => {
    void refresh();
    const expired = () => setUser(null);
    window.addEventListener("auth-expired", expired);
    return () => window.removeEventListener("auth-expired", expired);
  }, []);
  const updateUser = (next: User | null) => { requestVersion.current += 1; setLoading(false); setUser(next); };
  return <AuthContext.Provider value={{ user, loading, refresh, setUser: updateUser }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used within AuthProvider");
  return value;
}
