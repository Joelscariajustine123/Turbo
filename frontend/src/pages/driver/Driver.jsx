import { useEffect, useState } from 'react';
import { api, qs } from '../../api/client';
import { useAuth } from '../../auth/AuthContext';
import { ChangePassword } from '../Account';
import { GpsChip, LiveMap, OtpDialog, TripMetrics, useDriverLocation } from '../../components/Tracking';
import {
  Alert, BarChart, Empty, Field, Loading, Pager, Stat, StatusBadge, day, money, useAction, useApi, when,
} from '../../components/ui';

function RideCard({ ride, children }) {
  return (
    <div className="card ride-card">
      <div className="ride-info">
        <p><span className="dot dot-pickup" /> {ride.pickup_location}</p>
        <p><span className="dot dot-drop" /> {ride.drop_location}</p>
        <p className="muted small">
          {ride.car_type_display} · {ride.distance} km · {ride.payment_method_display || 'Unpaid'} · {when(ride.created_at)}
        </p>
        <p>
          <strong>{ride.rider.full_name}</strong>
          {ride.rider.phone && <> · <a href={`tel:${ride.rider.phone}`}>{ride.rider.phone}</a></>}
        </p>
      </div>
      <div className="ride-side">
        <strong className="fare-sm">{money(ride.fare)}</strong>
        <div className="actions">{children}</div>
      </div>
    </div>
  );
}

export function Dashboard() {
  const profile = useApi('/driver/profile/');
  const available = useApi('/driver/rides/available/', { pollMs: 10000 });
  const ongoing = useApi('/driver/rides/ongoing/', { pollMs: 10000 });
  const unpaid = useApi('/driver/rides/unpaid/', { pollMs: 20000 });
  const { data: meta } = useApi('/meta/');
  const act = useAction();
  const [notice, setNotice] = useState('');
  const [otpFor, setOtpFor] = useState(null);
  const [tracking, setTracking] = useState(null);

  const refresh = () => Promise.all([available.reload(true), ongoing.reload(true), profile.reload(true), unpaid.reload(true)]);
  const status = profile.data?.availability_status;
  // Share GPS every 3 s whenever the driver is online (the rider sees it during a trip).
  const location = useDriverLocation(!!status && status !== 'offline', (data) => {
    setTracking(data.tracking);
    if ((data.tracking?.status || null) !== (ongoing.data?.results[0]?.status || null)) ongoing.reload(true);
  });

  // 50 m rule: the server decides; buttons unlock when the latest GPS fix is close enough.
  const geo = (r) => (tracking && tracking.ride_id === r.id && tracking.geofence) || {};
  const lockText = (r, place) => {
    const g = geo(r);
    if (g.reason === 'imprecise') return `GPS ±${Math.round(g.accuracy_m || 0)} m, too imprecise`;
    if (g.distance_m == null) return 'waiting for GPS';
    return `${g.distance_m < 1000 ? `${g.distance_m} m` : `${(g.distance_m / 1000).toFixed(1)} km`} away · unlocks within ${g.radius_m} m of the ${place}`;
  };

  const statusAction = (id, value, message) =>
    act.run(async () => {
      await api('/driver/ride/status/', { method: 'POST', body: { ride_id: id, status: value } });
      setNotice(message);
      await refresh();
    });

  const rideAction = (id, action, message) =>
    act.run(async () => {
      await api(`/driver/rides/${id}/${action}/`, { method: 'POST' });
      setNotice(message);
      await refresh();
    });

  const setAvailability = (value) =>
    act.run(async () => {
      profile.setData(await api('/driver/profile/', { method: 'PATCH', body: { availability_status: value } }));
    });

  return (
    <div className="stack">
      <div className="page-head">
        <h1>Dashboard</h1>
        <GpsChip {...location} />
        {profile.data && (
          <label className={`availability av-${status}`}>
            Status
            <select value={status} disabled={act.busy} onChange={(e) => setAvailability(e.target.value)}>
              {(meta?.availability_statuses || []).map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </label>
        )}
      </div>
      <Alert>{act.error}</Alert>
      <Alert kind="success">{notice}</Alert>
      {profile.data && (!profile.data.license_number || !profile.data.vehicle_info) && (
        <Alert kind="info">Add your licence and vehicle details on the Profile page so riders know what to look for.</Alert>
      )}

      <section>
        <h2>Ongoing rides</h2>
        {ongoing.loading && !ongoing.data ? <Loading /> : ongoing.data?.results.length ? (
          ongoing.data.results.map((r) => (
            <div key={r.id} className="stack">
              <RideCard ride={r}>
                <StatusBadge status={r.status} label={r.status_display} />
                {r.status === 'ACCEPTED' && (
                  <button className="btn primary" disabled={act.busy || !geo(r).within}
                    onClick={() => statusAction(r.id, 'ARRIVED', 'Marked as arrived. Ask the rider for their OTP.')}>
                    {geo(r).within ? "I've arrived" : `I've arrived · ${lockText(r, 'pickup')}`}
                  </button>
                )}
                {r.status === 'ARRIVED' && (
                  <button className="btn primary" disabled={act.busy} onClick={() => setOtpFor(r.id)}>Verify OTP</button>
                )}
                {r.status === 'IN_PROGRESS' && (
                  <button className="btn success" disabled={act.busy || !geo(r).within}
                    onClick={() => rideAction(r.id, 'complete', 'Ride completed. The rider now pays by UPI or cash.')}>
                    {geo(r).within ? 'Complete ride' : `Complete · ${lockText(r, 'destination')}`}
                  </button>
                )}
              </RideCard>
              {tracking && tracking.ride_id === r.id && (
                <>
                  <TripMetrics t={tracking} />
                  <LiveMap tracking={tracking} me={location.fix} />
                </>
              )}
            </div>
          ))
        ) : <Empty>No ongoing rides.</Empty>}
      </section>

      {unpaid.data?.results.length > 0 && (
        <section>
          <h2>Awaiting payment</h2>
          {unpaid.data.results.map((r) => (
            <RideCard key={r.id} ride={r}>
              <span className="muted small">{r.payment_status === 'CASH_DUE' ? 'Rider chose cash' : "Rider hasn't paid yet"}</span>
              <button className="btn success" disabled={act.busy}
                onClick={() => window.confirm(`Did you receive ${money(r.fare)} in cash?`) &&
                  rideAction(r.id, 'cash-collected', 'Cash payment recorded.')}>
                Cash collected
              </button>
            </RideCard>
          ))}
        </section>
      )}

      <section>
        <div className="page-head">
          <h2>New ride requests</h2>
          <button className="btn ghost small" onClick={refresh}>Refresh</button>
        </div>
        {status === 'offline' && <Alert kind="info">You are offline. Switch to Available to accept rides.</Alert>}
        {available.loading && !available.data ? <Loading /> : available.data?.results.length ? (
          available.data.results.map((r) => (
            <RideCard key={r.id} ride={r}>
              <button className="btn success" disabled={act.busy || status === 'offline'}
                onClick={() => rideAction(r.id, 'accept', 'Ride accepted! Head to the pickup point.')}>
                Accept
              </button>
              <button className="btn danger ghost" disabled={act.busy}
                onClick={() => rideAction(r.id, 'decline', 'Ride declined.')}>
                Decline
              </button>
            </RideCard>
          ))
        ) : <Empty>No new ride requests right now. This list refreshes automatically.</Empty>}
      </section>
      {otpFor && (
        <OtpDialog rideId={otpFor} onClose={() => setOtpFor(null)}
          onVerified={() => { setOtpFor(null); setNotice('Passenger verified. Ride started — head to the destination.'); refresh(); }} />
      )}
    </div>
  );
}

export function Earnings() {
  const { data, error, loading } = useApi('/driver/earnings/');
  if (loading && !data) return <Loading />;
  if (error) return <Alert>{error.message}</Alert>;

  const rows = data.chart.map((r) => ({
    label: new Date(r.date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }),
    value: Number(r.total),
  }));

  return (
    <div className="stack">
      <h1>Earnings</h1>
      <div className="stats">
        <Stat label="Today" value={money(data.daily_earnings)} />
        <Stat label="Last 7 days" value={money(data.weekly_earnings)} />
        <Stat label="Last 30 days" value={money(data.monthly_earnings)} />
        <Stat label="All time" value={money(data.total_earnings)} />
        <Stat label="Completed rides" value={data.completed_rides} />
        <Stat label="Rating" value={data.average_rating ? `${data.average_rating.toFixed(1)} ★` : '—'} />
      </div>
      <div className="card">
        <h3>Daily earnings (last 30 days)</h3>
        <BarChart rows={rows} format={(v) => `₹${Math.round(v)}`} />
      </div>
      <div className="card">
        <h3>Recent earnings</h3>
        {data.recent.length ? (
          <table className="table">
            <thead><tr><th>Date</th><th>Rider</th><th>Trip</th><th className="num">Amount</th></tr></thead>
            <tbody>
              {data.recent.map((e) => (
                <tr key={e.id}>
                  <td>{day(e.date)}</td>
                  <td>{e.rider_name || '—'}</td>
                  <td className="truncate">{e.pickup_location ? `${e.pickup_location} → ${e.drop_location}` : '—'}</td>
                  <td className="num">{money(e.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : <Empty>Complete a ride to see earnings here.</Empty>}
      </div>
    </div>
  );
}

export function History() {
  const [page, setPage] = useState(1);
  const { data, error, loading } = useApi(`/driver/rides/history/${qs({ page })}`);
  return (
    <div className="stack">
      <h1>Ride history</h1>
      <Alert>{error?.message}</Alert>
      {loading && !data ? <Loading /> : data?.results.length ? (
        <div className="card">
          <table className="table">
            <thead><tr><th>Date</th><th>Rider</th><th>Trip</th><th>Status</th><th className="num">Fare</th></tr></thead>
            <tbody>
              {data.results.map((r) => (
                <tr key={r.id}>
                  <td>{when(r.created_at)}</td>
                  <td>{r.rider.full_name}</td>
                  <td className="truncate">{r.pickup_location} → {r.drop_location}</td>
                  <td><StatusBadge status={r.status} label={r.status_display} /></td>
                  <td className="num">{money(r.fare)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <Empty>No completed rides yet.</Empty>}
      <Pager data={data} page={page} onPage={setPage} />
    </div>
  );
}

export function Profile() {
  const { updateUser, user } = useAuth();
  const { data, error, loading } = useApi('/driver/profile/');
  const { data: meta } = useApi('/meta/');
  const [form, setForm] = useState(null);
  const [photo, setPhoto] = useState(null);
  const [notice, setNotice] = useState('');
  const save = useAction();

  useEffect(() => {
    if (data) {
      setForm({
        full_name: data.full_name, phone: data.phone || '', email: data.email,
        license_number: data.license_number, vehicle_info: data.vehicle_info,
        vehicle_number: data.vehicle_number || '', vehicle_type: data.vehicle_type || '',
        availability_status: data.availability_status,
      });
    }
  }, [data]);

  if (loading || !form) return error ? <Alert>{error.message}</Alert> : <Loading />;

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const submit = (e) => {
    e.preventDefault();
    setNotice('');
    save.run(async () => {
      const body = new FormData();
      Object.entries(form).forEach(([k, v]) => body.append(k, v));
      if (photo) body.append('profile_photo', photo);
      const updated = await api('/driver/profile/', { method: 'PATCH', body });
      updateUser({ ...user, full_name: updated.full_name, email: updated.email, phone: updated.phone });
      setPhoto(null);
      setNotice('Profile saved.');
    });
  };

  return (
    <div className="stack narrow">
    <form className="stack" onSubmit={submit}>
      <h1>Profile</h1>
      <Alert>{save.error}</Alert>
      <Alert kind="success">{notice}</Alert>
      <div className="card">
        <div className="photo-row">
          {data.profile_photo ? <img src={data.profile_photo} alt="Profile" className="avatar" /> : <div className="avatar placeholder">{form.full_name[0]}</div>}
          <Field label="Profile photo">
            <input type="file" accept="image/*" onChange={(e) => setPhoto(e.target.files[0] || null)} />
          </Field>
        </div>
        <Field label="Full name"><input required value={form.full_name} onChange={set('full_name')} /></Field>
        <div className="row-2">
          <Field label="Phone"><input required inputMode="numeric" pattern="[0-9]{10}" maxLength={10} value={form.phone} onChange={set('phone')} /></Field>
          <Field label="Email"><input type="email" required value={form.email} onChange={set('email')} /></Field>
        </div>
        <div className="row-2">
          <Field label="Licence number"><input required value={form.license_number} onChange={set('license_number')} /></Field>
          <Field label="Vehicle model"><input required value={form.vehicle_info} onChange={set('vehicle_info')} /></Field>
        </div>
        <div className="row-2">
          <Field label="Registration number">
            <input value={form.vehicle_number} maxLength={20} style={{ textTransform: 'uppercase' }} onChange={set('vehicle_number')} />
          </Field>
          <Field label="Vehicle type">
            <select value={form.vehicle_type} onChange={set('vehicle_type')}>
              <option value="">— Select —</option>
              {(meta?.car_types || []).map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
            </select>
          </Field>
        </div>
        <Field label="Availability">
          <select value={form.availability_status} onChange={set('availability_status')}>
            {(meta?.availability_statuses || []).map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
        </Field>
        <button className="btn primary" disabled={save.busy}>{save.busy ? 'Saving…' : 'Save changes'}</button>
      </div>
    </form>
    <ChangePassword />
    </div>
  );
}
