import { useState } from 'react';
import { api } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { Alert, Field, useAction } from '../components/ui';

export function ChangePassword() {
  const [pw, setPw] = useState({ old_password: '', new_password: '' });
  const [done, setDone] = useState(false);
  const { busy, error, run } = useAction();

  const submit = (e) => {
    e.preventDefault();
    setDone(false);
    run(async () => {
      await api('/auth/change-password/', { method: 'POST', body: pw });
      setPw({ old_password: '', new_password: '' });
      setDone(true);
    });
  };

  return (
    <form className="card" onSubmit={submit}>
      <h3>Change password</h3>
      <Alert>{error}</Alert>
      {done && <Alert kind="success">Password changed.</Alert>}
      <Field label="Current password">
        <input type="password" required autoComplete="current-password" value={pw.old_password}
          onChange={(e) => setPw({ ...pw, old_password: e.target.value })} />
      </Field>
      <Field label="New password">
        <input type="password" required autoComplete="new-password" value={pw.new_password}
          onChange={(e) => setPw({ ...pw, new_password: e.target.value })} />
      </Field>
      <button className="btn primary" disabled={busy}>{busy ? 'Changing…' : 'Change password'}</button>
    </form>
  );
}

/** Profile + password for riders and admins (admins get extra content as children). */
export default function Account({ children }) {
  const { user, updateUser } = useAuth();
  const [profile, setProfile] = useState({ full_name: user.full_name, email: user.email, phone: user.phone || '' });
  const [saved, setSaved] = useState(false);
  const { busy, error, run } = useAction();

  const saveProfile = (e) => {
    e.preventDefault();
    setSaved(false);
    run(async () => {
      updateUser(await api('/auth/me/', { method: 'PATCH', body: profile }));
      setSaved(true);
    });
  };

  return (
    <div className="stack">
      <h1>Account</h1>
      <div className="grid-2">
        <form className="card" onSubmit={saveProfile}>
          <h3>Profile</h3>
          <Alert>{error}</Alert>
          {saved && <Alert kind="success">Profile saved.</Alert>}
          <Field label="Full name">
            <input required value={profile.full_name} onChange={(e) => setProfile({ ...profile, full_name: e.target.value })} />
          </Field>
          <Field label="Email">
            <input type="email" required value={profile.email} onChange={(e) => setProfile({ ...profile, email: e.target.value })} />
          </Field>
          <Field label="Phone">
            <input inputMode="numeric" maxLength={10} value={profile.phone}
              onChange={(e) => setProfile({ ...profile, phone: e.target.value })} />
          </Field>
          <button className="btn primary" disabled={busy}>{busy ? 'Saving…' : 'Save profile'}</button>
        </form>
        <ChangePassword />
      </div>
      {children}
    </div>
  );
}
