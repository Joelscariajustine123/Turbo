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

  // Login/register return {otp_required, challenge, email} when an emailed code is needed,
  // otherwise tokens. Callers get {pending} or {user}.
  const finish = useCallback((data) => (data.otp_required ? { pending: data } : { user: saveSession(data) }), [saveSession]);

  const login = useCallback(
    async (email, password, role) =>
      finish(await api('/auth/login/', { method: 'POST', body: { email, password, role }, auth: false })),
    [finish],
  );

  const register = useCallback(
    async (fields) => finish(await api('/auth/register/', { method: 'POST', body: fields, auth: false })),
    [finish],
  );

  const verifyEmail = useCallback(
    async (challenge, code) =>
      saveSession(await api('/auth/verify-email/', { method: 'POST', body: { challenge, code }, auth: false })),
    [saveSession],
  );

  const resendCode = useCallback(
    (challenge) => api('/auth/resend-code/', { method: 'POST', body: { challenge }, auth: false }),
    [],
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
    () => ({ user, login, register, verifyEmail, resendCode, logout, updateUser }),
    [user, login, register, verifyEmail, resendCode, logout, updateUser],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}

export const homeFor = (role) => ({ rider: '/rider', driver: '/driver', admin: '/admin' })[role] || '/';
