// Small fetch wrapper for the Turbo API: adds the JWT, refreshes it once on 401,
// and turns error responses into ApiError with a readable message.

const BASE = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '');
const STORAGE_KEY = 'turbo.auth';

export class ApiError extends Error {
  constructor(message, status, data) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

export const session = {
  get() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY));
    } catch {
      return null;
    }
  },
  set(value) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
    } catch {
      /* storage unavailable: session lasts for this tab only */
    }
  },
  clear() {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      /* ignore */
    }
  },
};

let refreshing = null;

function refreshAccessToken() {
  const current = session.get();
  if (!current?.refresh) return Promise.reject(new ApiError('Not logged in', 401));
  refreshing ||= fetch(`${BASE}/api/auth/refresh/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh: current.refresh }),
  })
    .then(async (res) => {
      if (!res.ok) throw new ApiError('Your session has expired. Please log in again.', 401);
      const data = await res.json();
      session.set({ ...current, access: data.access, refresh: data.refresh || current.refresh });
    })
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

export async function api(path, { method = 'GET', body, auth = true, retry = true } = {}) {
  const headers = { Accept: 'application/json' };
  let payload = body;
  if (body !== undefined && !(body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
    payload = JSON.stringify(body);
  }
  const current = session.get();
  if (auth && current?.access) headers.Authorization = `Bearer ${current.access}`;

  let res;
  try {
    res = await fetch(`${BASE}/api${path}`, { method, headers, body: payload });
  } catch {
    throw new ApiError("Can't reach the server. Check that Django is running.", 0);
  }

  if (res.status === 401 && auth && retry && current?.refresh) {
    try {
      await refreshAccessToken();
    } catch (err) {
      session.clear();
      window.dispatchEvent(new Event('turbo:logout'));
      throw err;
    }
    return api(path, { method, body, auth, retry: false });
  }

  if (res.status === 204 || res.status === 205) return null;
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(data?.detail || `Request failed (${res.status})`, res.status, data);
  return data;
}

export function qs(params) {
  const entries = Object.entries(params).filter(([, v]) => v !== '' && v !== null && v !== undefined);
  return entries.length ? `?${new URLSearchParams(entries)}` : '';
}
