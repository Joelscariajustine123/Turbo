import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { api, session } from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => session.get()?.user ?? null);

  const saveSession = useCallback((data) => {
    session.set({ access: data.access, refresh: data.refresh, user: data.user });
    setUser(data.user);
    return data.user;
  }, []);

  const login = useCallback(
    async (email, password, role) =>
      saveSession(await api('/auth/login/', { method: 'POST', body: { email, password, role }, auth: false })),
    [saveSession],
  );

  const register = useCallback(
    async (fields) => saveSession(await api('/auth/register/', { method: 'POST', body: fields, auth: false })),
    [saveSession],
  );

  const logout = useCallback(async () => {
    const refresh = session.get()?.refresh;
    session.clear();
    setUser(null);
    if (refresh) api('/auth/logout/', { method: 'POST', body: { refresh }, auth: false }).catch(() => {});
  }, []);

  const updateUser = useCallback((next) => {
    const current = session.get();
    if (current) session.set({ ...current, user: next });
    setUser(next);
  }, []);

  // The API client fires this when the refresh token is no longer valid.
  useEffect(() => {
    const onExpired = () => setUser(null);
    window.addEventListener('turbo:logout', onExpired);
    return () => window.removeEventListener('turbo:logout', onExpired);
  }, []);

  const value = useMemo(
    () => ({ user, login, register, logout, updateUser }),
    [user, login, register, logout, updateUser],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}

export const homeFor = (role) => ({ rider: '/rider', driver: '/driver', admin: '/admin' })[role] || '/';
