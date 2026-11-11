import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../api/client';

export const money = (v) => `₹${Number(v ?? 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export const when = (iso) =>
  iso ? new Date(iso).toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : '—';

export const day = (iso) =>
  iso ? new Date(iso).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '—';

/** GET `path` (re-fetches when it changes). Optional `pollMs` refreshes in the background. */
export function useApi(path, { pollMs } = {}) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const pathRef = useRef(path);
  pathRef.current = path;

  const load = useCallback(async (quiet = false) => {
    if (!pathRef.current) return;
    if (!quiet) setState((s) => ({ ...s, loading: true }));
    try {
      const data = await api(pathRef.current);
      setState({ data, error: null, loading: false });
    } catch (error) {
      setState((s) => ({ ...s, error, loading: false }));
    }
  }, []);

  useEffect(() => {
    load();
  }, [path, load]);

  useEffect(() => {
    if (!pollMs) return undefined;
    const id = setInterval(() => {
      if (document.visibilityState === 'visible') load(true);
    }, pollMs);
    return () => clearInterval(id);
  }, [pollMs, load]);

  return { ...state, reload: load, setData: (data) => setState((s) => ({ ...s, data })) };
}

/** Wraps an async action with busy + error state, for buttons and forms. */
export function useAction() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const run = useCallback(async (fn) => {
    setBusy(true);
    setError('');
    try {
      return await fn();
    } catch (err) {
      setError(err.message || 'Something went wrong.');
      return undefined;
    } finally {
      setBusy(false);
    }
  }, []);
  return { busy, error, setError, run };
}

export function Alert({ kind = 'error', children }) {
  if (!children) return null;
  return (
    <div className={`alert alert-${kind}`} role={kind === 'error' ? 'alert' : 'status'}>
      {children}
    </div>
  );
}

export function Loading({ label = 'Loading…' }) {
  return <p className="muted loading">{label}</p>;
}

export function StatusBadge({ status, label }) {
  return <span className={`badge badge-${(status || '').toLowerCase()}`}>{label || status}</span>;
}

export function Stat({ label, value, hint }) {
  return (
    <div className="stat">
      <span className="stat-label">{label}</span>
      <strong className="stat-value">{value}</strong>
      {hint && <span className="stat-hint">{hint}</span>}
    </div>
  );
}

export function Empty({ children }) {
  return <p className="empty">{children}</p>;
}

/** Prev / next controls for DRF page-number pagination. */
export function Pager({ data, page, onPage }) {
  if (!data || (!data.next && !data.previous)) return null;
  return (
    <div className="pager">
      <button className="btn ghost" disabled={!data.previous} onClick={() => onPage(page - 1)}>
        ← Previous
      </button>
      <span className="muted">
        Page {page} · {data.count} total
      </span>
      <button className="btn ghost" disabled={!data.next} onClick={() => onPage(page + 1)}>
        Next →
      </button>
    </div>
  );
}

export function Field({ label, children, hint }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {hint && <small className="muted">{hint}</small>}
    </label>
  );
}

/** Simple bar chart from [{label, value}] (no chart library needed). */
export function BarChart({ rows, format = (v) => v }) {
  if (!rows?.length) return <Empty>No data to chart yet.</Empty>;
  const max = Math.max(...rows.map((r) => r.value), 1);
  return (
    <div className="bars" role="img" aria-label="Bar chart">
      {rows.map((r) => (
        <div className="bar-col" key={r.label} title={`${r.label}: ${format(r.value)}`}>
          <span className="bar-value">{format(r.value)}</span>
          <div className="bar" style={{ height: `${Math.max((r.value / max) * 100, 2)}%` }} />
          <span className="bar-label">{r.label}</span>
        </div>
      ))}
    </div>
  );
}
