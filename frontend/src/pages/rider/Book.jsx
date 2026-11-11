import { useEffect, useState } from 'react';
import { CircleMarker, MapContainer, Polyline, TileLayer, Tooltip, useMap, useMapEvents } from 'react-leaflet';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api/client';
import { currentPosition, reverseGeocode } from '../../api/geo';
import PlaceSearch from '../../components/PlaceSearch';
import { Alert, money, useAction, useApi } from '../../components/ui';

const KANNUR = [11.8745, 75.3704];

function ClickToPick({ onPick }) {
  useMapEvents({ click: (e) => onPick(e.latlng) });
  return null;
}

function FitTo({ points }) {
  const map = useMap();
  const key = JSON.stringify(points);
  useEffect(() => {
    if (points.length === 1) map.setView(points[0], 15);
    if (points.length > 1) map.fitBounds(points, { padding: [40, 40] });
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}

export default function Book() {
  const navigate = useNavigate();
  const { data: meta } = useApi('/meta/');
  const [pickup, setPickup] = useState(null);
  const [drop, setDrop] = useState(null);
  const [picking, setPicking] = useState('drop');
  const [quote, setQuote] = useState(null);
  const [car, setCar] = useState('sedan');
  const [notice, setNotice] = useState('Finding your location…');
  const quoting = useAction();
  const booking = useAction();

  useEffect(() => {
    currentPosition()
      .then(async (p) => {
        setNotice('');
        // Don't overwrite a pickup the rider already chose while we were waiting.
        setPickup((cur) => cur || { ...p, label: 'Current location' });
        const label = await reverseGeocode(p.lat, p.lng);
        setPickup((cur) => (cur && cur.lat === p.lat && cur.lng === p.lng ? { ...cur, label } : cur));
      })
      .catch((err) => {
        setNotice(err.message);
        setPicking('pickup');
      });
  }, []);

  // Ask the server for distance + fares whenever both points are set.
  useEffect(() => {
    setQuote(null);
    if (!pickup || !drop) return undefined;
    let stale = false;
    quoting.run(async () => {
      const q = await api('/rider/quote/', {
        method: 'POST',
        body: { pickup_lat: pickup.lat, pickup_lng: pickup.lng, drop_lat: drop.lat, drop_lng: drop.lng },
      });
      if (!stale) setQuote(q);
    });
    return () => {
      stale = true;
    };
  }, [pickup?.lat, pickup?.lng, drop?.lat, drop?.lng]); // eslint-disable-line react-hooks/exhaustive-deps

  const pickOnMap = async ({ lat, lng }) => {
    const point = { lat, lng, label: 'Looking up address…' };
    const setter = picking === 'pickup' ? setPickup : setDrop;
    setter(point);
    if (picking === 'pickup') setPicking('drop');
    const label = await reverseGeocode(lat, lng);
    setter((cur) => (cur && cur.lat === lat && cur.lng === lng ? { ...cur, label } : cur));
  };

  const book = () =>
    booking.run(async () => {
      const ride = await api('/rider/rides/', {
        method: 'POST',
        body: {
          pickup: pickup.label, drop: drop.label, car_type: car,
          pickup_lat: pickup.lat, pickup_lng: pickup.lng, drop_lat: drop.lat, drop_lng: drop.lng,
        },
      });
      navigate(`/rider/rides/${ride.id}`);
    });

  const points = [pickup, drop].filter(Boolean).map((p) => [p.lat, p.lng]);
  const line = quote?.geometry?.length ? quote.geometry : points;

  return (
    <div className="book">
      <aside className="card book-panel">
        <h2>Book your ride</h2>
        <Alert kind="info">{notice}</Alert>

        <div className="point">
          <div className="point-head">
            <span className="dot dot-pickup" /> Pickup
            <button type="button" className={`chip ${picking === 'pickup' ? 'on' : ''}`} onClick={() => setPicking('pickup')}>
              Set on map
            </button>
          </div>
          <PlaceSearch placeholder="Search pickup" value={pickup?.label} onSelect={(p) => { setPickup(p); setPicking('drop'); }} />
        </div>

        <div className="point">
          <div className="point-head">
            <span className="dot dot-drop" /> Drop
            <button type="button" className={`chip ${picking === 'drop' ? 'on' : ''}`} onClick={() => setPicking('drop')}>
              Set on map
            </button>
          </div>
          <PlaceSearch placeholder="Where to?" value={drop?.label} onSelect={setDrop} />
        </div>

        <p className="muted small">Tap the map to set the {picking} point.</p>

        <Alert>{quoting.error || booking.error}</Alert>
        {quoting.busy && <p className="muted">Calculating fare…</p>}

        {quote && (
          <>
            <p className="distance">
              {quote.distance_km} km {quote.source === 'estimate' && <span className="muted">(estimated)</span>}
            </p>
            <div className="cars">
              {(meta?.car_types || []).map((c) => (
                <label key={c.value} className={`car ${car === c.value ? 'on' : ''}`}>
                  <input type="radio" name="car" value={c.value} checked={car === c.value} onChange={() => setCar(c.value)} />
                  <span>{c.label}</span>
                  <strong>{money(quote.fares[c.value])}</strong>
                </label>
              ))}
            </div>
            <button className="btn primary block" disabled={booking.busy} onClick={book}>
              {booking.busy ? 'Booking…' : `Confirm booking · ${money(quote.fares[car])}`}
            </button>
          </>
        )}
      </aside>

      <div className="map-wrap">
        <MapContainer center={KANNUR} zoom={13} className="map">
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <ClickToPick onPick={pickOnMap} />
          <FitTo points={points} />
          {pickup && (
            <CircleMarker center={[pickup.lat, pickup.lng]} radius={9} pathOptions={{ color: '#fff', fillColor: '#22c55e', fillOpacity: 1 }}>
              <Tooltip>Pickup</Tooltip>
            </CircleMarker>
          )}
          {drop && (
            <CircleMarker center={[drop.lat, drop.lng]} radius={9} pathOptions={{ color: '#fff', fillColor: '#ef4444', fillOpacity: 1 }}>
              <Tooltip>Drop</Tooltip>
            </CircleMarker>
          )}
          {pickup && drop && <Polyline positions={line} pathOptions={{ color: '#3b82f6', weight: 5, opacity: 0.85 }} />}
        </MapContainer>
      </div>
    </div>
  );
}
