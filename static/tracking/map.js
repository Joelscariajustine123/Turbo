/* Turbo live map — one small API over Google Maps or Leaflet/OpenStreetMap.
 *
 *   const map = await TurboMap.create(element, { provider: 'google'|'osm', mapId, center: [lat, lng] });
 *   map.setMarker('driver', {lat, lng}, { kind: 'car', heading: 90 });   // creates or animates
 *   map.setRoute('route', [[lat, lng], ...], { color: '#3b82f6' });
 *   map.fit([{lat, lng}, ...]);
 *
 * Markers are updated in place (never re-created) and glide between positions.
 */
(function () {
  'use strict';

  var CAR_SVG =
    '<svg viewBox="0 0 48 48" width="40" height="40" aria-hidden="true">' +
    '<circle cx="24" cy="24" r="22" fill="rgba(59,130,246,.18)"/>' +
    '<g class="trk-car-body">' +
    '<path d="M24 6 L33 38 L24 32 L15 38 Z" fill="#3b82f6" stroke="#fff" stroke-width="2.5" stroke-linejoin="round"/>' +
    '</g></svg>';

  function markerHtml(kind, label) {
    if (kind === 'car') return '<div class="trk-mk trk-mk-car">' + CAR_SVG + '</div>';
    if (kind === 'pickup') return '<div class="trk-mk trk-mk-pin trk-mk-pickup"><span>' + (label || 'P') + '</span></div>';
    if (kind === 'drop') return '<div class="trk-mk trk-mk-pin trk-mk-drop"><span>' + (label || 'D') + '</span></div>';
    return '<div class="trk-mk trk-mk-dot"></div>';
  }

  function makeEl(kind, label) {
    var wrap = document.createElement('div');
    wrap.innerHTML = markerHtml(kind, label);
    return wrap.firstChild;
  }

  function rotate(el, heading) {
    if (heading === null || heading === undefined || isNaN(heading)) return;
    var body = el.querySelector('.trk-car-body');
    if (body) body.setAttribute('transform', 'rotate(' + heading + ' 24 24)');
  }

  var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Glide a marker from its current position to `to` over `ms`.
  function animate(getPos, setPos, to, ms, state) {
    if (state.raf) cancelAnimationFrame(state.raf);
    var from = getPos();
    if (!from || reduceMotion || ms <= 0) { setPos(to); return; }
    var start = performance.now();
    function step(now) {
      var t = Math.min(1, (now - start) / ms);
      var e = t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t; // easeInOutQuad
      setPos({ lat: from.lat + (to.lat - from.lat) * e, lng: from.lng + (to.lng - from.lng) * e });
      if (t < 1) state.raf = requestAnimationFrame(step);
    }
    state.raf = requestAnimationFrame(step);
  }

  function routeKey(coords) {
    if (!coords || !coords.length) return '';
    var a = coords[0], b = coords[coords.length - 1];
    return coords.length + ':' + a[0].toFixed(5) + ',' + a[1].toFixed(5) + ':' + b[0].toFixed(5) + ',' + b[1].toFixed(5);
  }

  /* ------------------------------------------------------------- Leaflet / OSM */
  function LeafletAdapter(el, cfg) {
    var map = L.map(el, { zoomControl: true, attributionControl: true }).setView(cfg.center, cfg.zoom || 14);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors',
    }).addTo(map);
    var markers = {}, routes = {};

    this.provider = 'osm';
    this.raw = map;
    this.setMarker = function (id, pos, opts) {
      opts = opts || {};
      var m = markers[id];
      if (!m) {
        var icon = L.divIcon({ html: markerHtml(opts.kind, opts.label), className: 'trk-mk-wrap', iconSize: [44, 44],
          iconAnchor: opts.kind === 'car' || !opts.kind ? [22, 22] : [22, 40] });
        m = markers[id] = { lm: L.marker([pos.lat, pos.lng], { icon: icon, title: opts.title || '', keyboard: false }).addTo(map), anim: {} };
        if (opts.title) m.lm.bindTooltip(opts.title);
      } else {
        animate(function () { var p = m.lm.getLatLng(); return { lat: p.lat, lng: p.lng }; },
          function (p) { m.lm.setLatLng([p.lat, p.lng]); }, pos, opts.animateMs === undefined ? 2500 : opts.animateMs, m.anim);
      }
      var el2 = m.lm.getElement();
      if (el2) rotate(el2, opts.heading);
    };
    this.removeMarker = function (id) { if (markers[id]) { map.removeLayer(markers[id].lm); delete markers[id]; } };
    this.setRoute = function (id, coords, opts) {
      opts = opts || {};
      var key = routeKey(coords);
      if (routes[id] && routes[id].key === key) return;
      this.removeRoute(id);
      if (!coords || coords.length < 2) return;
      routes[id] = { key: key, layer: L.polyline(coords, { color: opts.color || '#3b82f6', weight: opts.weight || 6,
        opacity: opts.opacity || 0.9, dashArray: opts.dashed ? '8 10' : null, lineCap: 'round' }).addTo(map) };
    };
    this.removeRoute = function (id) { if (routes[id]) { map.removeLayer(routes[id].layer); delete routes[id]; } };
    this.fit = function (points, padding) {
      var pts = points.filter(Boolean).map(function (p) { return [p.lat, p.lng]; });
      if (pts.length === 1) map.setView(pts[0], Math.max(map.getZoom(), 15));
      else if (pts.length > 1) map.fitBounds(pts, { padding: [padding || 60, padding || 60], maxZoom: 16 });
    };
    this.contains = function (p) { return map.getBounds().pad(-0.1).contains([p.lat, p.lng]); };
    this.panTo = function (p) { map.panTo([p.lat, p.lng]); };
    this.resize = function () { map.invalidateSize(); };
    this.onUserMove = function (cb) { map.on('dragstart', cb); };
  }

  /* ------------------------------------------------------------- Google Maps */
  function GoogleAdapter(el, cfg) {
    var g = google.maps;
    var map = new g.Map(el, {
      center: { lat: cfg.center[0], lng: cfg.center[1] }, zoom: cfg.zoom || 14, mapId: cfg.mapId || 'DEMO_MAP_ID',
      streetViewControl: false, mapTypeControl: false, fullscreenControl: false, clickableIcons: false,
      gestureHandling: 'greedy',
    });
    var markers = {}, routes = {};
    var Advanced = g.marker && g.marker.AdvancedMarkerElement;

    this.provider = 'google';
    this.raw = map;
    this.setMarker = function (id, pos, opts) {
      opts = opts || {};
      var m = markers[id];
      if (!m) {
        var el2 = makeEl(opts.kind, opts.label);
        var gm = Advanced
          ? new Advanced({ map: map, position: pos, content: el2, title: opts.title || '' })
          : new g.Marker({ map: map, position: pos, title: opts.title || '' });
        m = markers[id] = { gm: gm, el: el2, anim: {} };
      } else {
        animate(function () {
          var p = m.gm.position;
          if (!p) return null;
          return typeof p.lat === 'function' ? { lat: p.lat(), lng: p.lng() } : { lat: p.lat, lng: p.lng };
        }, function (p) { if (Advanced) m.gm.position = p; else m.gm.setPosition(p); },
        pos, opts.animateMs === undefined ? 2500 : opts.animateMs, m.anim);
      }
      rotate(m.el, opts.heading);
    };
    this.removeMarker = function (id) { if (markers[id]) { markers[id].gm.map = null; if (markers[id].gm.setMap) markers[id].gm.setMap(null); delete markers[id]; } };
    this.setRoute = function (id, coords, opts) {
      opts = opts || {};
      var key = routeKey(coords);
      if (routes[id] && routes[id].key === key) return;
      this.removeRoute(id);
      if (!coords || coords.length < 2) return;
      var path = coords.map(function (c) { return { lat: c[0], lng: c[1] }; });
      var line = opts.dashed
        ? new g.Polyline({ path: path, map: map, strokeOpacity: 0, icons: [{ icon: { path: 'M 0,-1 0,1', strokeOpacity: 0.9,
            strokeColor: opts.color || '#64748b', scale: 3 }, offset: '0', repeat: '14px' }] })
        : new g.Polyline({ path: path, map: map, strokeColor: opts.color || '#3b82f6', strokeOpacity: opts.opacity || 0.9,
            strokeWeight: opts.weight || 6 });
      routes[id] = { key: key, line: line };
    };
    this.removeRoute = function (id) { if (routes[id]) { routes[id].line.setMap(null); delete routes[id]; } };
    this.fit = function (points, padding) {
      var pts = points.filter(Boolean);
      if (pts.length === 1) { map.setCenter(pts[0]); if (map.getZoom() < 15) map.setZoom(15); }
      else if (pts.length > 1) {
        var b = new g.LatLngBounds();
        pts.forEach(function (p) { b.extend(p); });
        map.fitBounds(b, padding || 60);
      }
    };
    this.contains = function (p) { var b = map.getBounds(); return !b || b.contains(p); };
    this.panTo = function (p) { map.panTo(p); };
    this.resize = function () {};
    this.onUserMove = function (cb) { map.addListener('dragstart', cb); };
  }

  /* ------------------------------------------------------------- loader */
  var googleReady = null;
  function loadGoogle(key) {
    if (window.google && window.google.maps && window.google.maps.Map) return Promise.resolve();
    if (googleReady) return googleReady;
    googleReady = new Promise(function (resolve, reject) {
      window.__turboGoogleReady = resolve;
      var s = document.createElement('script');
      s.src = 'https://maps.googleapis.com/maps/api/js?key=' + encodeURIComponent(key) +
        '&v=weekly&libraries=marker&loading=async&callback=__turboGoogleReady';
      s.async = true;
      s.onerror = function () { reject(new Error('Google Maps failed to load')); };
      document.head.appendChild(s);
    });
    return googleReady;
  }

  function loadLeaflet() {
    if (window.L && window.L.map) return Promise.resolve();
    return new Promise(function (resolve, reject) {
      var css = document.createElement('link');
      css.rel = 'stylesheet';
      css.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
      document.head.appendChild(css);
      var s = document.createElement('script');
      s.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
      s.onload = resolve;
      s.onerror = function () { reject(new Error('Map library failed to load')); };
      document.head.appendChild(s);
    });
  }

  // Google calls this when the API key is invalid/restricted; after that the map stops
  // working, so remember it for this session and reload on OpenStreetMap instead.
  var FALLBACK_FLAG = 'turbo.maps.googleFailed';
  window.gm_authFailure = function () {
    console.warn('Google Maps rejected the API key (check GOOGLE_MAPS_API_KEY, billing and allowed referrers). ' +
      'Switching to OpenStreetMap.');
    try {
      if (!sessionStorage.getItem(FALLBACK_FLAG)) { sessionStorage.setItem(FALLBACK_FLAG, '1'); window.location.reload(); }
    } catch (e) { /* storage blocked: stay on the broken map rather than reload-looping */ }
  };
  function googleFailedBefore() {
    try { return sessionStorage.getItem(FALLBACK_FLAG) === '1'; } catch (e) { return false; }
  }

  window.TurboMap = {
    create: function (el, cfg) {
      cfg = cfg || {};
      cfg.center = cfg.center || [11.8745, 75.3704]; // Kannur
      if (cfg.provider === 'google' && cfg.googleKey && !googleFailedBefore()) {
        return loadGoogle(cfg.googleKey).then(function () { return new GoogleAdapter(el, cfg); })
          .catch(function () {
            // Bad/missing key or blocked script: fall back to OpenStreetMap.
            return loadLeaflet().then(function () { return new LeafletAdapter(el, cfg); });
          });
      }
      return loadLeaflet().then(function () { return new LeafletAdapter(el, cfg); });
    },
    navigateUrl: function (from, to) {
      var u = 'https://www.google.com/maps/dir/?api=1&travelmode=driving&destination=' + to.lat + ',' + to.lng;
      if (from) u += '&origin=' + from.lat + ',' + from.lng;
      return u;
    },
  };
})();
