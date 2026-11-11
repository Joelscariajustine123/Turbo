/* Shared helpers for the live tracking pages (session-authenticated API calls). */
(function () {
  'use strict';

  function cookie(name) {
    var m = document.cookie.match('(?:^|; )' + name + '=([^;]*)');
    return m ? decodeURIComponent(m[1]) : '';
  }

  function ApiError(message, status, data) {
    this.message = message; this.status = status; this.data = data || {};
  }

  /** fetch JSON from /api with the logged-in session, CSRF header and a timeout. */
  function api(path, opts) {
    opts = opts || {};
    var ctrl = new AbortController();
    var timer = setTimeout(function () { ctrl.abort(); }, opts.timeout || 8000);
    var headers = { Accept: 'application/json' };
    var body;
    if (opts.body !== undefined) { headers['Content-Type'] = 'application/json'; body = JSON.stringify(opts.body); }
    if (opts.method && opts.method !== 'GET') headers['X-CSRFToken'] = cookie('csrftoken');
    return fetch('/api' + path, { method: opts.method || 'GET', headers: headers, body: body, credentials: 'same-origin',
      signal: ctrl.signal, cache: 'no-store' })
      .then(function (res) {
        return res.text().then(function (text) {
          var data = null;
          try { data = text ? JSON.parse(text) : null; } catch (e) { data = null; }
          if (!res.ok) throw new ApiError((data && data.detail) || ('Request failed (' + res.status + ')'), res.status, data);
          return data;
        });
      }, function (err) {
        throw new ApiError(err && err.name === 'AbortError' ? 'The server took too long to respond.' : 'No connection.', 0);
      })
      .finally(function () { clearTimeout(timer); });
  }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function km(v) { return v == null ? '—' : (v < 1 ? Math.round(v * 1000) + ' m' : v.toFixed(1) + ' km'); }

  function ago(seconds) {
    if (seconds == null) return '—';
    if (seconds < 5) return 'just now';
    if (seconds < 60) return Math.round(seconds) + ' s ago';
    return Math.round(seconds / 60) + ' min ago';
  }

  function clock(iso) {
    if (!iso) return '';
    return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  /** Run `fn` every `ms`, never overlapping: the next run waits for the previous one. */
  function loop(fn, ms) {
    var stopped = false, timer = null;
    function run() {
      if (stopped) return;
      var started = Date.now();
      Promise.resolve().then(fn).catch(function () {}).then(function () {
        if (!stopped) timer = setTimeout(run, Math.max(0, ms - (Date.now() - started)));
      });
    }
    run();
    return {
      stop: function () { stopped = true; clearTimeout(timer); },
      now: function () { clearTimeout(timer); run(); },
    };
  }

  function toast(text, kind) {
    var box = document.getElementById('trk-toasts');
    if (!box) return;
    var el = document.createElement('div');
    el.className = 'trk-toast trk-toast-' + (kind || 'info');
    el.textContent = text;
    box.appendChild(el);
    setTimeout(function () { el.classList.add('out'); }, 3800);
    setTimeout(function () { el.remove(); }, 4300);
  }

  var lastGeocode = { at: 0, lat: 0, lng: 0, text: '' };
  /** Address for a point via OpenStreetMap Nominatim (max once / 30 s, as their policy asks). */
  function reverseGeocode(lat, lng) {
    var moved = Math.abs(lat - lastGeocode.lat) + Math.abs(lng - lastGeocode.lng) > 0.0008;
    if (lastGeocode.text && (!moved || Date.now() - lastGeocode.at < 30000)) return Promise.resolve(lastGeocode.text);
    lastGeocode.at = Date.now(); lastGeocode.lat = lat; lastGeocode.lng = lng;
    return fetch('https://nominatim.openstreetmap.org/reverse?format=json&zoom=17&lat=' + lat + '&lon=' + lng,
      { headers: { 'Accept-Language': 'en' } })
      .then(function (r) { return r.json(); })
      .then(function (d) { lastGeocode.text = d.display_name || ''; return lastGeocode.text; })
      .catch(function () { return lastGeocode.text; });
  }

  window.Trk = { api: api, ApiError: ApiError, esc: esc, km: km, ago: ago, clock: clock, loop: loop, toast: toast,
    reverseGeocode: reverseGeocode };
})();
