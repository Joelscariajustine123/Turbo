import { useEffect, useState } from 'react';
import { Link, Navigate, useLocation, useNavigate, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { homeFor, useAuth } from '../auth/AuthContext';
import { Alert, Field, useAction } from '../components/ui';

const ROLES = {
  rider: { title: 'Rider', blurb: 'Book rides and track your trips' },
  driver: { title: 'Driver', blurb: 'Accept rides and track earnings' },
  admin: { title: 'Admin', blurb: 'Manage riders, drivers and bookings' },
};

export function Landing() {
  const { user } = useAuth();
  if (user) return <Navigate to={homeFor(user.role)} replace />;
  return (
    <div className="center-page">
      <div className="hero">
        <h1>
          Ride with <span className="accent">Turbo</span>
        </h1>
        <p className="muted">Tap. Ride. Arrive. Choose how you want to continue.</p>
        <div className="role-grid">
          {Object.entries(ROLES).map(([role, r]) => (
            <Link key={role} to={`/login/${role}`} className={`role-card role-${role}`}>
              <strong>{r.title}</strong>
              <span>{r.blurb}</span>
            </Link>
          ))}
        </div>
        <Link to="/contact" className="muted small-link">
          Contact us
        </Link>
      </div>
    </div>
  );
}

/** "Check your email" step shared by login and registration. */
function EmailCode({ pending, onDone, onBack }) {
  const { verifyEmail, resendCode } = useAuth();
  const [code, setCode] = useState('');
  const [info, setInfo] = useState('');
  const [wait, setWait] = useState(60);
  const { busy, error, run } = useAction();
  useEffect(() => {
    if (wait <= 0) return undefined;
    const t = setTimeout(() => setWait((w) => w - 1), 1000);
    return () => clearTimeout(t);
  }, [wait]);
  const submit = (e) => {
    e?.preventDefault();
    run(async () => onDone(await verifyEmail(pending.challenge, code)));
  };
  return (
    <form className="card auth-card" onSubmit={submit}>
      <h2>{pending.purpose === 'register' ? 'Verify your email' : 'Check your email'}</h2>
      <p className="muted">We sent a 6-digit code to <strong>{pending.email}</strong>. It expires in 10 minutes.</p>
      <Alert>{error}</Alert>
      <Alert kind="success">{info}</Alert>
      <input className="otp-input" inputMode="numeric" autoComplete="one-time-code" maxLength={6} autoFocus required
        aria-label="6-digit code" placeholder="••••••" value={code}
        onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))} />
      <button className="btn primary block" disabled={busy || code.length !== 6}>{busy ? 'Checking…' : 'Verify'}</button>
      <button type="button" className="btn ghost block" disabled={wait > 0 || busy}
        onClick={() => run(async () => { const r = await resendCode(pending.challenge); setInfo(r.detail); setWait(60); })}>
        {wait > 0 ? `Resend code in ${wait}s` : 'Resend code'}
      </button>
      <p className="center"><button type="button" className="btn ghost small" onClick={onBack}>← Back</button></p>
    </form>
  );
}

export function Login() {
  const { role } = useParams();
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [form, setForm] = useState({ email: '', password: '' });
  const [pending, setPending] = useState(null);
  const { busy, error, run } = useAction();

  if (!ROLES[role]) return <Navigate to="/" replace />;
  if (user) return <Navigate to={homeFor(user.role)} replace />;

  const go = (u) => navigate(location.state?.from?.startsWith(homeFor(u.role)) ? location.state.from : homeFor(u.role),
    { replace: true });
  const submit = (e) => {
    e.preventDefault();
    run(async () => {
      const r = await login(form.email.trim(), form.password, role);
      if (r.pending) setPending(r.pending); else go(r.user);
    });
  };

  if (pending) {
    return <div className="center-page"><EmailCode pending={pending} onDone={go} onBack={() => setPending(null)} /></div>;
  }

  return (
    <div className="center-page">
      <form className="card auth-card" onSubmit={submit}>
        <h2>{ROLES[role].title} log in</h2>
        <Alert>{error}</Alert>
        <Field label="Email">
          <input type="email" autoComplete="email" required value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })} />
        </Field>
        <Field label="Password">
          <input type="password" autoComplete="current-password" required value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })} />
        </Field>
        <button className="btn primary block" disabled={busy}>
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
        <p className="muted center">
          {role !== 'admin' ? (
            <>
              New here? <Link to={`/register/${role}`}>Create a {role} account</Link>
            </>
          ) : (
            'Admin accounts are created by an existing admin.'
          )}
        </p>
        <p className="center">
          <Link to="/" className="muted">
            ← Choose a different role
          </Link>
        </p>
      </form>
    </div>
  );
}

export function Register() {
  const { role } = useParams();
  const { user, register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ full_name: '', username: '', email: '', phone: '', password: '', password2: '' });
  const [pending, setPending] = useState(null);
  const { busy, error, setError, run } = useAction();

  if (role !== 'rider' && role !== 'driver') return <Navigate to="/" replace />;
  if (user) return <Navigate to={homeFor(user.role)} replace />;

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const submit = (e) => {
    e.preventDefault();
    if (form.password !== form.password2) {
      setError('Passwords do not match.');
      return;
    }
    const { password2, ...body } = form;
    run(async () => {
      const r = await register({ ...body, role });
      if (r.pending) setPending(r.pending); else done(r.user);
    });
  };
  function done(u) { navigate(role === 'driver' ? '/driver/profile' : homeFor(u.role), { replace: true }); }

  if (pending) {
    return <div className="center-page"><EmailCode pending={pending} onDone={done} onBack={() => setPending(null)} /></div>;
  }

  return (
    <div className="center-page">
      <form className="card auth-card" onSubmit={submit}>
        <h2>Create a {ROLES[role].title.toLowerCase()} account</h2>
        <Alert>{error}</Alert>
        <Field label="Full name">
          <input required value={form.full_name} onChange={set('full_name')} autoComplete="name" />
        </Field>
        <div className="row-2">
          <Field label="Username">
            <input required value={form.username} onChange={set('username')} autoComplete="username" />
          </Field>
          <Field label="Phone">
            <input inputMode="numeric" pattern="[0-9]{10}" maxLength={10} title="10-digit phone number"
              required value={form.phone} onChange={set('phone')} autoComplete="tel" />
          </Field>
        </div>
        <Field label="Email">
          <input type="email" required value={form.email} onChange={set('email')} autoComplete="email" />
        </Field>
        <div className="row-2">
          <Field label="Password">
            <input type="password" required value={form.password} onChange={set('password')} autoComplete="new-password" />
          </Field>
          <Field label="Repeat password">
            <input type="password" required value={form.password2} onChange={set('password2')} autoComplete="new-password" />
          </Field>
        </div>
        <button className="btn primary block" disabled={busy}>
          {busy ? 'Creating account…' : 'Create account'}
        </button>
        <p className="muted center">
          Already registered? <Link to={`/login/${role}`}>Log in</Link>
        </p>
      </form>
    </div>
  );
}

export function Contact() {
  const [form, setForm] = useState({ name: '', email: '', message: '' });
  const [sent, setSent] = useState(false);
  const { busy, error, run } = useAction();
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = (e) => {
    e.preventDefault();
    run(async () => {
      await api('/contact/', { method: 'POST', body: form, auth: false });
      setSent(true);
      setForm({ name: '', email: '', message: '' });
    });
  };

  return (
    <div className="center-page">
      <form className="card auth-card" onSubmit={submit}>
        <h2>Contact us</h2>
        <p className="muted">Anjarakandy 670612, Kannur, Kerala · Turbocabs@gmail.com</p>
        <Alert>{error}</Alert>
        {sent && <Alert kind="success">Thanks! Your message has been sent.</Alert>}
        <Field label="Your name">
          <input required maxLength={100} value={form.name} onChange={set('name')} />
        </Field>
        <Field label="Email">
          <input type="email" required value={form.email} onChange={set('email')} />
        </Field>
        <Field label="Message">
          <textarea required rows={4} value={form.message} onChange={set('message')} />
        </Field>
        <button className="btn primary block" disabled={busy}>
          {busy ? 'Sending…' : 'Send message'}
        </button>
        <p className="center">
          <Link to="/" className="muted">
            ← Back
          </Link>
        </p>
      </form>
    </div>
  );
}
