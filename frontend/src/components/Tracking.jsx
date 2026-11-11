// Live tracking for the React app: driver location sender, live map, OTP card and OTP dialog.
// Uses the same /api endpoints as the Django website and the mobile apps.
import L from 'leaflet';
import { useEffect, useMemo, useRef, useState } from 'react';
import { MapContainer, Marker, Polyline, TileLayer, useMap } from 'react-leaflet';
import { api } from '../api/client';
import { Alert, useAction } from './ui';

/* ------------------------------------------------------------------ driver GPS */

/**
 * While `enabled`, watches the device GPS and POSTs the latest fix every 3 s
 * (requests never overlap). Returns live status plus the server's tracking reply.
 */
export function useDriverLocation(enabled, onTracking) {
  const [gps, setGps] = useState('idle');
  const [net, setNet] = useState('ok');
  const [lastSentAt, setLastSentAt] = useState(null);
  const fix = useRef(null);
  const cb = useRef(onTracking);
  cb.current = onTracking;

  useEffect(() => {
    if (!enabled) { setGps('idle'); return undefined; }
    if (!('geolocation' in navigator)) { setGps('unsupported'); return undefined; }
    setGps('waiting');
    const watch = navigator.geolocation.watchPosition(
      (pos) => {
        const c = pos.coords;
        fix.current = {
          latitude: +c.latitude.toFixed(6), longitude: +c.longitude.toFixed(6),
          accuracy: c.accuracy != null ? Math.round(c.accuracy) : null,
          speed: c.speed != null && c.speed >= 0 ? +(c.speed * 3.6).toFixed(1) : null,
          heading: c.heading != null && !Number.isNaN(c.heading) ? Math.round(c.heading) : null,
          at: Date.now(),
        };
        setGps('ok');
      },
      (err) => setGps(err.code === 1 ? 'denied' : err.code === 2 ? 'unavailable' : 'weak'),
      { enableHighAccuracy: true, maximumAge: 2000, timeout: 20000 },
    );

    let stopped = false;
    let timer;
    const tick = async () => {
      const started = Date.now();
      const f = fix.current;
      if (f) {
        if (Date.now() - f.at > 15000) setGps('weak');
        try {
          const { at, ...body } = f;
          const data = await api('/driver/location/update/', { method: 'POST', body });
          setNet('ok');
          setLastSentAt(Date.now());
          cb.current?.(data);
        } catch (e) {
          setNet(e.status === 409 ? 'offline-driver' : navigator.onLine ? 'error' : 'offline');
        }
      }
      if (!stopped) timer = setTimeout(tick, Math.max(0, 3000 - (Date.now() - started)));
    };
    tick();
    const wake = () => { clearTimeout(timer); tick(); };
    window.addEventListener('online', wake);
    return () => {
      stopped = true;
      clearTimeout(timer);
      navigator.geolocation.clearWatch(watch);
      window.removeEventListener('online', wake);
    };
  }, [enabled]);

  return { gps, net, lastSentAt, fix: fix.current };
}

export function GpsChip({ gps, net, lastSentAt }) {
  const [, force] = useState(0);
  useEffect(() => { const t = setInterval(() => force((n) => n + 1), 1000); return () => clearInterval(t); }, []);
  const map = {
    idle: ['', 'Location off'], waiting: ['warn', 'Finding GPS…'], ok: ['ok', 'GPS live'], weak: ['warn', 'GPS signal weak'],
    denied: ['bad', 'Location blocked — allow it in browser settings'], unavailable: ['bad', 'GPS unavailable'],
    unsupported: ['bad', 'No GPS in this browser'],
  };
  const [cls, text] = map[gps] || map.idle;
  const age = lastSentAt ? Math.round((Date.now() - lastSentAt) / 1000) : null;
  return (
    <span className={`gps-chip ${net !== 'ok' && gps !== 'idle' ? 'bad' : cls}`}>
      {gps === 'ok' && <span className="pulse" />}
      {net === 'offline' || net === 'error' ? 'No connection — retrying' : text}
      {gps === 'ok' && net === 'ok' && age != null && <small> · sent {age < 5 ? 'just now' : `${age}s ago`}</small>}
    </span>
  );
}

/* ------------------------------------------------------------------ map */

const icon = (kind, heading) => L.divIcon({
  className: 'live-mk',
  iconSize: [40, 40],
  iconAnchor: kind === 'car' ? [20, 20] : [20, 38],
  html: kind === 'car'
    ? `<svg viewBox="0 0 48 48" width="40" height="40"><circle cx="24" cy="24" r="22" fill="rgba(59,130,246,.2)"/><path transform="rotate(${heading || 0} 24 24)" d="M24 6 L33 38 L24 32 L15 38 Z" fill="#3b82f6" stroke="#fff" stroke-width="2.5" stroke-linejoin="round"/></svg>`
    : `<div class="live-pin ${kind}"><span>${kind === 'pickup' ? 'P' : 'D'}</span></div>`,
});

/** Glides a Leaflet marker between positions instead of jumping. */
function GlidingMarker({ position, heading }) {
  const ref = useRef(null);
  const last = useRef(position);
  const markerIcon = useMemo(() => icon('car', heading), [heading]);
  useEffect(() => {
    const m = ref.current;
    if (!m) return undefined;
    const from = last.current;
    last.current = position;
    if (!from || window.matchMedia('(prefers-reduced-motion: reduce)').matches) { m.setLatLng(position); return undefined; }
    const start = performance.now();
    let raf;
    const step = (now) => {
      const t = Math.min(1, (now - start) / 2500);
      m.setLatLng([from[0] + (position[0] - from[0]) * t, from[1] + (position[1] - from[1]) * t]);
      if (t < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [position[0], position[1]]); // eslint-disable-line react-hooks/exhaustive-deps
  return <Marker ref={ref} position={last.current || position} icon={markerIcon} />;
}

function AutoFit({ points, fitKey }) {
  const map = useMap();
  useEffect(() => {
    const pts = points.filter(Boolean);
    if (pts.length === 1) map.setView(pts[0], 15);
    else if (pts.length > 1) map.fitBounds(pts, { padding: [50, 50], maxZoom: 16 });
  }, [fitKey]); // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}

/** Live map from a tracking payload (same shape for driver and rider). */
export function LiveMap({ tracking, me, height = 380 }) {
  const t = tracking || {};
  const car = t.driver_location ? [t.driver_location.lat, t.driver_location.lng] : me ? [me.latitude, me.longitude] : null;
  const heading = t.driver_location?.heading ?? me?.heading;
  const pickup = t.pickup && [t.pickup.lat, t.pickup.lng];
  const drop = t.drop && [t.drop.lat, t.drop.lng];
  const target = t.stage === 'destination' ? drop : pickup;
  return (
    <div className="live-map" style={{ height }}>
      <MapContainer center={car || pickup || [11.8745, 75.3704]} zoom={14} style={{ height: '100%' }}>
        <TileLayer url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" maxZoom={19}
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' />
        <AutoFit points={[car, target]} fitKey={`${t.ride_id}:${t.stage}:${car ? 1 : 0}`} />
        {t.stage === 'pickup' && t.trip_route && (
          <Polyline positions={t.trip_route.geometry} pathOptions={{ color: '#94a3b8', dashArray: '8 10', weight: 5 }} />
        )}
        {t.route && <Polyline positions={t.route.geometry} pathOptions={{ color: '#3b82f6', weight: 6, opacity: 0.9 }} />}
        {pickup && <Marker position={pickup} icon={icon('pickup')} />}
        {drop && <Marker position={drop} icon={icon('drop')} />}
        {car && <GlidingMarker position={car} heading={heading} />}
      </MapContainer>
    </div>
  );
}

export function TripMetrics({ t }) {
  if (!t || !t.stage) return null;
  const km = (v) => (v == null ? '—' : v < 1 ? `${Math.round(v * 1000)} m` : `${v.toFixed(1)} km`);
  return (
    <div className="stats compact">
      <div className="stat"><span className="stat-label">To pickup</span><strong className="stat-value">
        {t.status === 'IN_PROGRESS' ? 'Picked up' : t.status === 'ARRIVED' ? 'Here' : km(t.distance_to_pickup_km)}</strong></div>
      <div className="stat"><span className="stat-label">To drop</span><strong className="stat-value">{km(t.distance_to_destination_km)}</strong></div>
      <div className="stat"><span className="stat-label">ETA</span><strong className="stat-value">
        {t.eta_minutes == null ? '—' : t.status === 'ARRIVED' ? 'Now' : `${t.eta_minutes} min`}</strong></div>
    </div>
  );
}

/* ------------------------------------------------------------------ OTP */

/** Rider: shows the pickup code for their own ride (before the ride starts). */
export function OtpCard({ rideId, status }) {
  const [otp, setOtp] = useState(null);
  const [now, setNow] = useState(Date.now());
  const regen = useAction();

  useEffect(() => {
    let alive = true;
    const load = () => api(`/rider/ride/otp/?ride_id=${rideId}`).then((o) => alive && setOtp(o)).catch(() => alive && setOtp(null));
    load();
    const t = setInterval(load, 30000);
    return () => { alive = false; clearInterval(t); };
  }, [rideId, status]);
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(t); }, []);

  if (!otp) return null;
  const left = Math.round((new Date(otp.expires_at) - now) / 1000);
  const expired = otp.is_expired || left <= 0;
  return (
    <div className="card otp-card">
      <h3>Your ride verification OTP</h3>
      <div className={`otp-code ${expired ? 'expired' : ''}`}>{expired ? '••••••' : otp.otp}</div>
      <p className="muted small">
        {otp.is_locked ? 'Too many wrong attempts. Get a new code to try again.'
          : expired ? 'This code has expired.'
            : `Share this code with your driver only after you get in. Expires in ${Math.floor(left / 60)}:${String(left % 60).padStart(2, '0')}.`}
      </p>
      <Alert>{regen.error}</Alert>
      <button className={`btn ${expired || otp.is_locked ? 'primary' : 'ghost'} small`} disabled={regen.busy}
        onClick={() => regen.run(async () => setOtp(await api('/rider/ride/otp/regenerate/', { method: 'POST', body: { ride_id: rideId } })))}>
        Get a new code
      </button>
    </div>
  );
}

/** Driver: enter the rider's 6-digit code to start the ride. */
export function OtpDialog({ rideId, onClose, onVerified }) {
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    if (!/^\d{6}$/.test(code)) { setError("Enter the 6-digit code from the rider's screen."); return; }
    setBusy(true); setError('');
    try {
      await api('/driver/ride/verify-otp/', { method: 'POST', body: { ride_id: rideId, otp: code } });
      onVerified();
    } catch (err) {
      setError(err.message);
    } finally { setBusy(false); }
  };
  return (
    <div className="modal-backdrop" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <form className="card modal" onSubmit={submit}>
        <h3>Verify passenger OTP</h3>
        <p className="muted">Ask the rider for the 6-digit code shown on their screen.</p>
        <input className="otp-input" inputMode="numeric" autoComplete="one-time-code" maxLength={6} autoFocus value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))} aria-label="6-digit OTP" placeholder="••••••" />
        <Alert>{error}</Alert>
        <div className="actions">
          <button type="button" className="btn ghost" onClick={onClose}>Cancel</button>
          <button className="btn primary" disabled={busy}>{busy ? 'Verifying…' : 'Verify OTP'}</button>
        </div>
      </form>
    </div>
  );
}
