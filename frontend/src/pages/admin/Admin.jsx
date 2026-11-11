import { useEffect, useState } from 'react';
import { api, qs } from '../../api/client';
import {
  Alert, Empty, Field, Loading, Pager, Stat, StatusBadge, day, money, useAction, useApi, when,
} from '../../components/ui';
import Account from '../Account';

/** Search box that only updates the query after typing pauses. */
function useSearch() {
  const [text, setText] = useState('');
  const [search, setSearch] = useState('');
  useEffect(() => {
    const t = setTimeout(() => setSearch(text.trim()), 350);
    return () => clearTimeout(t);
  }, [text]);
  return { text, setText, search };
}

function RideTable({ rides, showPayment }) {
  return (
    <table className="table">
      <thead>
        <tr>
          <th>#</th><th>Booked</th><th>Rider</th><th>Driver</th><th>Trip</th>
          {showPayment && <th>Method</th>}<th>Status</th><th className="num">Fare</th>
        </tr>
      </thead>
      <tbody>
        {rides.map((r) => (
          <tr key={r.id}>
            <td>{r.id}</td>
            <td>{when(r.created_at)}</td>
            <td>{r.rider.full_name}</td>
            <td>{r.driver?.full_name || <span className="muted">—</span>}</td>
            <td className="truncate" title={`${r.pickup_location} → ${r.drop_location}`}>
              {r.pickup_location} → {r.drop_location}
            </td>
            {showPayment && <td>{r.payment_method_display || '—'}{r.transaction_id && <div className="muted small">{r.transaction_id}</div>}</td>}
            <td><StatusBadge status={r.status} label={r.status_display} /></td>
            <td className="num">{money(r.fare)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function Overview() {
  const { data, error, loading } = useApi('/admin/stats/', { pollMs: 30000 });
  if (loading && !data) return <Loading />;
  if (error) return <Alert>{error.message}</Alert>;
  return (
    <div className="stack">
      <h1>Overview</h1>
      <div className="stats">
        <Stat label="Revenue this month" value={money(data.monthly_revenue)} hint={`${money(data.total_revenue)} all time`} />
        <Stat label="Completed rides" value={data.total_bookings} hint={`${data.total_rides} booked in total`} />
        <Stat label="Awaiting payment" value={data.pending_requests} />
        <Stat label="Waiting for driver" value={data.waiting_for_driver} />
        <Stat label="On the road" value={data.ongoing_rides} />
        <Stat label="Riders / Drivers" value={`${data.total_riders} / ${data.total_drivers}`} />
      </div>
      <div className="card">
        <h3>Latest rides</h3>
        {data.recent_rides.length ? <RideTable rides={data.recent_rides} /> : <Empty>No rides yet.</Empty>}
      </div>
    </div>
  );
}

export function Rides({ payments = false }) {
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  const { text, setText, search } = useSearch();
  const { data: meta } = useApi('/meta/');
  const path = payments ? '/admin/rides/payments/' : '/admin/rides/';
  const { data, error, loading } = useApi(`${path}${qs({ status, search, page })}`);

  useEffect(() => setPage(1), [status, search]);

  return (
    <div className="stack">
      <div className="page-head">
        <h1>{payments ? 'Payments' : 'Rides'}</h1>
        <div className="filters">
          <input placeholder="Search place or name" value={text} onChange={(e) => setText(e.target.value)} />
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All statuses</option>
            {(meta?.ride_statuses || []).map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
        </div>
      </div>
      <Alert>{error?.message}</Alert>
      {loading && !data ? <Loading /> : data?.results.length ? (
        <div className="card scroll-x"><RideTable rides={data.results} showPayment={payments} /></div>
      ) : <Empty>No rides match.</Empty>}
      <Pager data={data} page={page} onPage={setPage} />
    </div>
  );
}

export function Reports() {
  const { data, error, loading } = useApi('/admin/reports/');
  return (
    <div className="stack">
      <h1>Daily reports</h1>
      <Alert>{error?.message}</Alert>
      {loading && !data ? <Loading /> : data?.length ? (
        <div className="card scroll-x">
          <table className="table">
            <thead><tr><th>Date</th><th className="num">Rides</th><th className="num">Completed</th><th className="num">Cancelled</th><th className="num">Revenue</th></tr></thead>
            <tbody>
              {data.map((r) => (
                <tr key={r.date}>
                  <td>{day(r.date)}</td>
                  <td className="num">{r.total_rides}</td>
                  <td className="num">{r.completed_rides}</td>
                  <td className="num">{r.cancelled_rides}</td>
                  <td className="num">{money(r.total_revenue)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <Empty>No ride data yet.</Empty>}
    </div>
  );
}

function RiderRow({ rider, onChanged, onDeleted }) {
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState(rider);
  const act = useAction();

  const save = (body) =>
    act.run(async () => {
      onChanged(await api(`/admin/riders/${rider.id}/`, { method: 'PATCH', body }));
      setEditing(false);
    });
  const remove = () =>
    window.confirm(`Delete ${rider.full_name}? Their rides will be deleted too.`) &&
    act.run(async () => {
      await api(`/admin/riders/${rider.id}/`, { method: 'DELETE' });
      onDeleted(rider.id);
    });

  if (editing) {
    return (
      <tr>
        <td><input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} /></td>
        <td><input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></td>
        <td><input value={form.phone} maxLength={10} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></td>
        <td colSpan={2}>
          {act.error && <div className="error-text">{act.error}</div>}
          <div className="actions">
            <button className="btn primary small" disabled={act.busy}
              onClick={() => save({ full_name: form.full_name, email: form.email, phone: form.phone })}>Save</button>
            <button className="btn ghost small" onClick={() => { setForm(rider); setEditing(false); }}>Cancel</button>
          </div>
        </td>
      </tr>
    );
  }
  return (
    <tr className={rider.is_active ? '' : 'inactive'}>
      <td>{rider.full_name}</td>
      <td>{rider.email}</td>
      <td>{rider.phone}</td>
      <td>{day(rider.date_joined)}</td>
      <td>
        {act.error && <div className="error-text">{act.error}</div>}
        <div className="actions">
          <button className="btn ghost small" onClick={() => setEditing(true)}>Edit</button>
          <button className="btn ghost small" disabled={act.busy} onClick={() => save({ is_active: !rider.is_active })}>
            {rider.is_active ? 'Deactivate' : 'Activate'}
          </button>
          <button className="btn danger ghost small" disabled={act.busy} onClick={remove}>Delete</button>
        </div>
      </td>
    </tr>
  );
}

export function Riders() {
  const [page, setPage] = useState(1);
  const { text, setText, search } = useSearch();
  const { data, error, loading, setData } = useApi(`/admin/riders/${qs({ search, page })}`);
  useEffect(() => setPage(1), [search]);

  const replace = (u) => setData({ ...data, results: data.results.map((r) => (r.id === u.id ? u : r)) });
  const drop = (id) => setData({ ...data, count: data.count - 1, results: data.results.filter((r) => r.id !== id) });

  return (
    <div className="stack">
      <div className="page-head">
        <h1>Riders {data && <span className="muted">({data.count})</span>}</h1>
        <input placeholder="Search name, email, phone" value={text} onChange={(e) => setText(e.target.value)} />
      </div>
      <Alert>{error?.message}</Alert>
      {loading && !data ? <Loading /> : data?.results.length ? (
        <div className="card scroll-x">
          <table className="table">
            <thead><tr><th>Name</th><th>Email</th><th>Phone</th><th>Joined</th><th /></tr></thead>
            <tbody>
              {data.results.map((r) => <RiderRow key={r.id} rider={r} onChanged={replace} onDeleted={drop} />)}
            </tbody>
          </table>
        </div>
      ) : <Empty>No riders found.</Empty>}
      <Pager data={data} page={page} onPage={setPage} />
    </div>
  );
}

export function Drivers() {
  const [page, setPage] = useState(1);
  const { text, setText, search } = useSearch();
  const { data, error, loading, setData } = useApi(`/admin/drivers/${qs({ search, page })}`);
  const { data: meta } = useApi('/meta/');
  const act = useAction();
  useEffect(() => setPage(1), [search]);

  const patch = (id, body) =>
    act.run(async () => {
      const u = await api(`/admin/drivers/${id}/`, { method: 'PATCH', body });
      setData({ ...data, results: data.results.map((d) => (d.id === id ? u : d)) });
    });
  const remove = (d) =>
    window.confirm(`Delete driver ${d.full_name}?`) &&
    act.run(async () => {
      await api(`/admin/drivers/${d.id}/`, { method: 'DELETE' });
      setData({ ...data, count: data.count - 1, results: data.results.filter((x) => x.id !== d.id) });
    });

  return (
    <div className="stack">
      <div className="page-head">
        <h1>Drivers {data && <span className="muted">({data.count})</span>}</h1>
        <input placeholder="Search name, vehicle, licence" value={text} onChange={(e) => setText(e.target.value)} />
      </div>
      <Alert>{error?.message || act.error}</Alert>
      {loading && !data ? <Loading /> : data?.results.length ? (
        <div className="card scroll-x">
          <table className="table">
            <thead><tr><th>Driver</th><th>Contact</th><th>Vehicle</th><th>Licence</th><th>Availability</th><th /></tr></thead>
            <tbody>
              {data.results.map((d) => (
                <tr key={d.id} className={d.is_active ? '' : 'inactive'}>
                  <td>
                    <div className="who-cell">
                      {d.profile_photo ? <img src={d.profile_photo} alt="" className="avatar sm" /> : <div className="avatar sm placeholder">{d.full_name[0]}</div>}
                      {d.full_name}
                    </div>
                  </td>
                  <td>{d.email}<div className="muted small">{d.phone}</div></td>
                  <td>{d.vehicle_info || '—'}</td>
                  <td>{d.license_number || '—'}</td>
                  <td>
                    <select value={d.availability_status} disabled={act.busy}
                      onChange={(e) => patch(d.id, { availability_status: e.target.value })}>
                      {(meta?.availability_statuses || []).map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
                    </select>
                  </td>
                  <td>
                    <div className="actions">
                      <button className="btn ghost small" disabled={act.busy} onClick={() => patch(d.id, { is_active: !d.is_active })}>
                        {d.is_active ? 'Deactivate' : 'Activate'}
                      </button>
                      <button className="btn danger ghost small" disabled={act.busy} onClick={() => remove(d)}>Delete</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <Empty>No drivers found.</Empty>}
      <Pager data={data} page={page} onPage={setPage} />
    </div>
  );
}

export function Messages() {
  const [page, setPage] = useState(1);
  const { data, error, loading, setData } = useApi(`/admin/messages/${qs({ page })}`);
  const act = useAction();
  const remove = (id) =>
    act.run(async () => {
      await api(`/admin/messages/${id}/`, { method: 'DELETE' });
      setData({ ...data, count: data.count - 1, results: data.results.filter((m) => m.id !== id) });
    });
  return (
    <div className="stack">
      <h1>Contact messages</h1>
      <Alert>{error?.message || act.error}</Alert>
      {loading && !data ? <Loading /> : data?.results.length ? (
        <div className="list">
          {data.results.map((m) => (
            <div key={m.id} className="card message">
              <div className="page-head">
                <div>
                  <strong>{m.name}</strong> · <a href={`mailto:${m.email}`}>{m.email}</a>
                  <div className="muted small">{when(m.created_at)}</div>
                </div>
                <button className="btn danger ghost small" disabled={act.busy} onClick={() => remove(m.id)}>Delete</button>
              </div>
              <p className="pre">{m.message}</p>
            </div>
          ))}
        </div>
      ) : <Empty>No messages.</Empty>}
      <Pager data={data} page={page} onPage={setPage} />
    </div>
  );
}

export function AdminAccount() {
  const empty = { full_name: '', username: '', email: '', password: '' };
  const [form, setForm] = useState(empty);
  const [notice, setNotice] = useState('');
  const act = useAction();
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const submit = (e) => {
    e.preventDefault();
    setNotice('');
    act.run(async () => {
      const u = await api('/admin/admins/', { method: 'POST', body: form });
      setForm(empty);
      setNotice(`Admin account created for ${u.email}.`);
    });
  };
  return (
    <Account>
      <form className="card" onSubmit={submit}>
        <h3>Add another admin</h3>
        <Alert>{act.error}</Alert>
        <Alert kind="success">{notice}</Alert>
        <div className="row-2">
          <Field label="Full name"><input required value={form.full_name} onChange={set('full_name')} /></Field>
          <Field label="Username"><input required value={form.username} onChange={set('username')} /></Field>
        </div>
        <div className="row-2">
          <Field label="Email"><input type="email" required value={form.email} onChange={set('email')} /></Field>
          <Field label="Temporary password"><input type="password" required autoComplete="new-password" value={form.password} onChange={set('password')} /></Field>
        </div>
        <button className="btn primary" disabled={act.busy}>{act.busy ? 'Creating…' : 'Create admin'}</button>
      </form>
    </Account>
  );
}
