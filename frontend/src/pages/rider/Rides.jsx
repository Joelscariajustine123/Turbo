import { QRCodeSVG } from 'qrcode.react';
import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api, qs } from '../../api/client';
import { upiLink } from '../../api/geo';
import { Alert, Empty, Loading, Pager, StatusBadge, money, useAction, useApi, when } from '../../components/ui';
import { LiveMap, OtpCard, TripMetrics } from '../../components/Tracking';

const ACTIVE = ['PENDING', 'CONFIRMED', 'ACCEPTED', 'ARRIVED', 'IN_PROGRESS'];
const TRIP = ['ACCEPTED', 'ARRIVED', 'IN_PROGRESS'];

export function RideList() {
  const [state, setState] = useState('');
  const [page, setPage] = useState(1);
  const { data, error, loading } = useApi(`/rider/rides/${qs({ state, page })}`, { pollMs: 15000 });

  return (
    <div className="stack">
      <div className="page-head">
        <h1>My rides</h1>
        <div className="tabs">
          {[['', 'All'], ['active', 'Active'], ['past', 'Past']].map(([v, l]) => (
            <button key={v} className={state === v ? 'on' : ''} onClick={() => { setState(v); setPage(1); }}>
              {l}
            </button>
          ))}
        </div>
      </div>
      <Alert>{error?.message}</Alert>
      {loading && !data ? (
        <Loading />
      ) : data?.results.length ? (
        <div className="list">
          {data.results.map((r) => (
            <Link key={r.id} to={`/rider/rides/${r.id}`} className="card ride-row">
              <div>
                <strong>{r.drop_location}</strong>
                <span className="muted">from {r.pickup_location}</span>
                <span className="muted small">{when(r.created_at)} · {r.car_type_display}</span>
              </div>
              <div className="ride-row-end">
                <strong>{money(r.fare)}</strong>
                <StatusBadge status={r.status} label={r.status_display} />
              </div>
            </Link>
          ))}
        </div>
      ) : (
        <Empty>
          No rides here yet. <Link to="/rider">Book one now</Link>.
        </Empty>
      )}
      <Pager data={data} page={page} onPage={setPage} />
    </div>
  );
}

function Stars({ onRate, busy }) {
  const [hover, setHover] = useState(0);
  return (
    <div className="stars" onMouseLeave={() => setHover(0)}>
      {[1, 2, 3, 4, 5].map((n) => (
        <button key={n} type="button" disabled={busy} aria-label={`${n} star${n > 1 ? 's' : ''}`}
          className={n <= hover ? 'on' : ''} onMouseEnter={() => setHover(n)} onClick={() => onRate(n)}>
          ★
        </button>
      ))}
    </div>
  );
}

export function RideDetail() {
  const { id } = useParams();
  const { data: ride, error, loading, setData, reload } = useApi(`/rider/rides/${id}/`, { pollMs: 10000 });
  const onTrip = ride && TRIP.includes(ride.status);
  const canPay = ride && (ride.status === 'PENDING' || ride.needs_payment);
  // Live driver position + route, every 3 s during the trip.
  const live = useApi(onTrip ? `/rider/ride/tracking/?ride_id=${id}` : null, { pollMs: 3000 });
  const { data: meta } = useApi('/meta/');
  const [showUpi, setShowUpi] = useState(false);
  const [txn, setTxn] = useState('');
  const act = useAction();

  if (loading && !ride) return <Loading />;
  if (error && !ride) return <Alert>{error.message}</Alert>;

  const post = (path, body) =>
    act.run(async () => {
      setData(await api(`/rider/rides/${id}/${path}/`, { method: 'POST', body }));
      setShowUpi(false);
    });

  return (
    <div className="stack narrow">
      <Link to="/rider/rides" className="muted">← My rides</Link>
      <div className="card">
        <div className="page-head">
          <h2>Ride #{ride.id}</h2>
          <StatusBadge status={ride.status} label={ride.status_display} />
        </div>
        <dl className="details">
          <dt>From</dt><dd>{ride.pickup_location}</dd>
          <dt>To</dt><dd>{ride.drop_location}</dd>
          <dt>Vehicle</dt><dd>{ride.car_type_display} · {ride.distance} km</dd>
          <dt>Booked</dt><dd>{when(ride.created_at)}</dd>
          {ride.payment_method && (<><dt>Payment</dt><dd>{ride.payment_method_display}{ride.transaction_id && ` · ${ride.transaction_id}`}</dd></>)}
        </dl>
        <p className="fare">{money(ride.fare)}</p>
        <Alert>{act.error}</Alert>

        {onTrip && !ride.otp_verified && (ride.status === 'ACCEPTED' || ride.status === 'ARRIVED') && (
          <OtpCard rideId={ride.id} status={ride.status} />
        )}
        {onTrip && live.data && (
          <>
            <p><strong>{live.data.stage_label}</strong>{live.data.driver_location?.is_stale && <span className="muted"> · driver GPS signal lost</span>}</p>
            <TripMetrics t={live.data} />
            <LiveMap tracking={live.data} height={340} />
          </>
        )}
        {ride.driver && (
          <div className="driver-box">
            {ride.driver.profile_photo && <img src={ride.driver.profile_photo} alt="" />}
            <div>
              <strong>{ride.driver.full_name}</strong>
              <span className="muted">{[ride.driver.vehicle_info, ride.driver.vehicle_type].filter(Boolean).join(' · ') || 'Vehicle details not added'}</span>
              {ride.driver.vehicle_number && <span className="plate">{ride.driver.vehicle_number}</span>}
              {ride.driver.phone && onTrip && <a href={`tel:${ride.driver.phone}`}>Call {ride.driver.phone}</a>}
            </div>
          </div>
        )}

        {ride.status === 'COMPLETED' && ride.payment_status === 'CASH_DUE' && (
          <Alert kind="info">Please pay {money(ride.fare)} to your driver in cash. They'll confirm once they've received it.</Alert>
        )}
        {ride.status === 'COMPLETED' && ride.payment_status === 'PAID' && (
          <Alert kind="success">Paid{ride.payment_method_display ? ` by ${ride.payment_method_display}` : ''} — thank you!</Alert>
        )}
        {canPay && !showUpi && <p className="muted">Your ride is complete. How would you like to pay?</p>}
        {canPay && !showUpi && (
          <div className="actions">
            <button className="btn primary" disabled={act.busy} onClick={() => setShowUpi(true)}>Pay with UPI</button>
            <button className="btn" disabled={act.busy} onClick={() => post('pay', { payment_method: 'cash' })}>Pay with cash</button>
          </div>
        )}

        {canPay && showUpi && meta && (
          <div className="upi">
            <QRCodeSVG value={upiLink(meta.upi_id, ride.fare, ride.id)} size={180} marginSize={2} bgColor="#ffffff" />
            <p>Scan with any UPI app, or pay to <strong>{meta.upi_id}</strong></p>
            <a className="btn ghost small" href={upiLink(meta.upi_id, ride.fare, ride.id)}>Open UPI app</a>
            <input placeholder="UPI transaction ID" value={txn} onChange={(e) => setTxn(e.target.value)} />
            <div className="actions">
              <button className="btn primary" disabled={act.busy || !txn.trim()}
                onClick={() => post('pay', { payment_method: 'upi', transaction_id: txn.trim() })}>
                Confirm payment
              </button>
              <button className="btn ghost" onClick={() => setShowUpi(false)}>Back</button>
            </div>
          </div>
        )}

        {ride.status === 'CONFIRMED' && <p className="muted">Waiting for a driver to accept your ride…</p>}

        {ride.status === 'COMPLETED' && (
          ride.rating ? (
            <p>You rated this ride <strong>{ride.rating} ★</strong></p>
          ) : (
            <div>
              <p>How was your ride?</p>
              <Stars busy={act.busy} onRate={(n) => post('rate', { rating: n })} />
            </div>
          )
        )}

        {ride.can_cancel && (
          <button className="btn danger ghost" disabled={act.busy}
            onClick={() => window.confirm('Cancel this ride?') && post('cancel')}>
            Cancel ride
          </button>
        )}
        {ACTIVE.includes(ride.status) && (
          <button className="btn ghost small" onClick={() => reload()}>Refresh</button>
        )}
      </div>
    </div>
  );
}
