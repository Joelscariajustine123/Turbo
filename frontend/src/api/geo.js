// Place search / address lookup via OpenStreetMap Nominatim (free, rate-limited:
// keep requests user-driven and debounced).
const NOMINATIM = 'https://nominatim.openstreetmap.org';

export async function searchPlaces(query, { signal } = {}) {
  const url = `${NOMINATIM}/search?format=json&limit=6&countrycodes=in&q=${encodeURIComponent(query)}`;
  const res = await fetch(url, { signal, headers: { 'Accept-Language': 'en' } });
  if (!res.ok) throw new Error('Search failed');
  const rows = await res.json();
  return rows.map((r) => ({ lat: Number(r.lat), lng: Number(r.lon), label: r.display_name }));
}

export async function reverseGeocode(lat, lng) {
  try {
    const res = await fetch(`${NOMINATIM}/reverse?format=json&lat=${lat}&lon=${lng}`, {
      headers: { 'Accept-Language': 'en' },
    });
    const data = await res.json();
    return data.display_name || `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
  } catch {
    return `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
  }
}

export function currentPosition() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error('Location is not available in this browser.'));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
      () => reject(new Error('Location access was denied. Search for your pickup instead.')),
      { enableHighAccuracy: true, timeout: 10000 },
    );
  });
}

export const upiLink = (upiId, amount, rideId) =>
  `upi://pay?pa=${encodeURIComponent(upiId)}&pn=${encodeURIComponent('Turbo Cabs')}&am=${Number(amount).toFixed(2)}` +
  `&tn=${encodeURIComponent(`Ride-${rideId}`)}&cu=INR`;
