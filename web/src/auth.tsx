import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { api, ApiError, type Me, type Status } from './api';

interface AuthState {
  status: Status | null;
  me: Me | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  login: (email: string, password: string, rememberMe: boolean, totpCode: string) => Promise<void>;
  bootstrap: (email: string, password: string, displayName: string) => Promise<void>;
  logout: () => Promise<void>;
}

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const s = await api.getStatus();
      setStatus(s);
      try {
        const m = await api.getMe();
        setMe(m);
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) setMe(null);
        else throw e;
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not reach the server');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const login = useCallback(
    async (email: string, password: string, rememberMe: boolean, totpCode: string) => {
      await api.login(email, password, rememberMe, totpCode);
      await refresh();
    },
    [refresh]
  );

  const bootstrap = useCallback(
    async (email: string, password: string, displayName: string) => {
      await api.bootstrap(email, password, displayName);
      await refresh();
    },
    [refresh]
  );

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      // logout is best-effort; local state must reset either way
    }
    setMe(null);
    await refresh();
  }, [refresh]);

  return (
    <Ctx.Provider value={{ status, me, loading, error, refresh, login, bootstrap, logout }}>
      {children}
    </Ctx.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
