/* Driver live location page.
 * - Watches the device GPS (watchPosition) and sends the latest fix every 3 s while online.
 * - Requests never overlap; failures retry on the next tick; tracking resumes when the network returns.
 * - The server's reply carries the active trip (pickup/destination, route, distance, ETA),
 *   so the driver sees exactly what the rider sees.
 */
(function () {
  'use strict';
  var cfg = JSON.parse(document.getElementById('trk-config').textContent);
  var $ = function (id) { return document.getElementById(id); };
  var api = Trk.api, esc = Trk.esc;

  var state = {
    online: cfg.availability !== 'offline',
    watchId: null, fix: null, fixAt: 0,
    gps: 'idle',            // idle | waiting | ok | weak | denied | unavailable | unsupported
    net: 'ok',              // ok | offline | error
    lastSentAt: 0, ride: null, rider: null, tracking: null,
    fittedFor: null, follow: true, wakeLock: null, loop: null,
  };
  var map = null;

  /* ---------------------------------------------------------- GPS */
  function startGps() {
    if (!('geolocation' in navigator)) { state.gps = 'unsupported'; renderStatus(); return; }
    if (state.watchId !== null) return;
    state.gps = 'waiting';
    renderStatus();
    state.watchId = navigator.geolocation.watchPosition(onFix, onGpsError,
      { enableHighAccuracy: true, maximumAge: 0, timeout: 20000 });
  }

  function stopGps() {
    if (state.watchId !== null) navigator.geolocation.clearWatch(state.watchId);
    state.watchId = null;
    state.gps = 'idle';
  }

  function onFix(pos) {
    var c = pos.coords;
    // A rough Wi-Fi/cell fix right after a good GPS one would make the car jump: skip it.
    if (c.accuracy > 150 && state.fix && state.fix.accuracy != null && state.fix.accuracy <= 150 &&
        Date.now() - state.fixAt < 20000) return;
    state.fix = {
      latitude: +c.latitude.toFixed(6), longitude: +c.longitude.toFixed(6),
      accuracy: c.accuracy != null ? Math.round(c.accuracy) : null,
      speed: c.speed != null && c.speed >= 0 ? +(c.speed * 3.6).toFixed(1) : null,  // m/s -> km/h
      heading: c.heading != null && !isNaN(c.heading) ? Math.round(c.heading) : null,
    };
    state.fixAt = Date.now();
    state.gps = 'ok';
    drawMe(true);
    renderCoords();
    Trk.reverseGeocode(state.fix.latitude, state.fix.longitude).then(function (addr) {
      if (addr) $('trk-address').textContent = addr;
    });
    renderStatus();
  }

  function onGpsError(err) {
    if (err.code === 1) { state.gps = 'denied'; stopGps(); state.gps = 'denied'; }
    else if (err.code === 2) state.gps = 'unavailable';
    else state.gps = state.fix ? 'weak' : 'waiting';
    renderStatus();
  }

  /* ---------------------------------------------------------- send loop (every 3 s) */
  function tick() {
    if (!state.online) return Promise.resolve();
    if (state.fix && Date.now() - state.fixAt > 15000 && state.gps === 'ok') state.gps = 'weak';
    renderStatus();
    var req = state.fix
      ? api('/driver/location/update/', { method: 'POST', body: state.fix })
      : api('/driver/active-ride/');  // no GPS yet: still keep the ride panel fresh
    return req.then(function (data) {
      state.net = 'ok';
      if (state.fix) state.lastSentAt = Date.now();
      if (data.tracking !== undefined && data.ride === undefined) {
        // location/update reply: refresh the full ride only when the trip changes
        var tr = data.tracking;
        if ((tr && (!state.tracking || state.tracking.status !== tr.status || state.tracking.ride_id !== tr.ride_id)) || (!tr && state.ride)) {
          return api('/driver/active-ride/').then(applyActiveRide);
        }
        state.tracking = tr;
        renderRide();
      } else {
        applyActiveRide(data);
      }
    }).catch(function (e) {
      if (e.status === 409) {           // server says we're offline
        setOnlineUi(false);
        stopTracking();
        Trk.toast(e.message, 'error');
      } else if (e.status === 401 || e.status === 403) {
        window.location.href = cfg.login_url;
      } else {
        state.net = navigator.onLine ? 'error' : 'offline';
      }
    }).then(renderStatus);
  }

  function applyActiveRide(data) {
    state.ride = data.ride; state.rider = data.rider || null; state.tracking = data.tracking;
    renderRide();
  }

  function startTracking() {
    startGps();
    if (!state.loop) state.loop = Trk.loop(tick, 3000);
    keepAwake();
  }

  function stopTracking() {
    if (state.loop) { state.loop.stop(); state.loop = null; }
    stopGps();
    releaseWake();
    renderStatus();
  }

  // Keep the screen on while tracking (best effort; browsers pause GPS when the screen locks).
  function keepAwake() {
    if (!('wakeLock' in navigator) || state.wakeLock) return;
    navigator.wakeLock.request('screen').then(function (lock) {
      state.wakeLock = lock;
      lock.addEventListener('release', function () { state.wakeLock = null; });
    }).catch(function () {});
  }
  function releaseWake() { if (state.wakeLock) { state.wakeLock.release().catch(function () {}); state.wakeLock = null; } }

  /* ---------------------------------------------------------- online toggle */
  function setOnlineUi(on) {
    state.online = on;
    $('trk-online').checked = on;
    $('trk-online-label').textContent = on ? 'Online' : 'Offline';
  }

  $('trk-online').addEventListener('change', function (e) {
    var want = e.target.checked;
    e.target.disabled = true;
    api('/driver/profile/', { method: 'PATCH', body: { availability_status: want ? 'available' : 'offline' } })
      .then(function () {
        setOnlineUi(want);
        if (want) { startTracking(); Trk.toast('You are online. Sharing your location.', 'success'); }
        else { stopTracking(); map && map.removeMarker('me'); Trk.toast('You are offline. Location sharing stopped.'); }
      })
      .catch(function (err) { setOnlineUi(!want); Trk.toast(err.message, 'error'); })
      .then(function () { e.target.disabled = false; });
  });

  /* ---------------------------------------------------------- ride actions */
  function rideAction(path, body, done) {
    return api(path, { method: 'POST', body: body }).then(function (data) {
      if (done) Trk.toast(done, 'success');
      return api('/driver/active-ride/').then(applyActiveRide).then(function () { return data; });
    });
  }

  $('trk-ride').addEventListener('click', function (e) {
    var btn = e.target.closest('[data-act]');
    if (!btn || !state.ride) return;
    var id = state.ride.id;
    if (btn.dataset.act === 'arrived') {
      btn.disabled = true;
      rideAction('/driver/ride/status/', { ride_id: id, status: 'ARRIVED' }, 'Marked as arrived. Ask the rider for their OTP.')
        .catch(function (err) { Trk.toast(err.message, 'error'); }).then(function () { btn.disabled = false; });
    } else if (btn.dataset.act === 'otp') {
      openOtp();
    } else if (btn.dataset.act === 'complete') {
      if (!window.confirm('Mark this ride as completed?')) return;
      btn.disabled = true;
      var fare = state.ride.fare, method = state.ride.payment_method_display;
      rideAction('/driver/ride/status/', { ride_id: id, status: 'COMPLETED' })
        .then(function () {
          Trk.toast('Ride completed. ₹' + Number(fare || 0).toFixed(2) + ' — the rider now pays by UPI or cash (confirm cash on your dashboard).', 'success');
          ['pickup', 'drop'].forEach(function (k) { map && map.removeMarker(k); });
          ['route', 'trip'].forEach(function (k) { map && map.removeRoute(k); });
        })
        .catch(function (err) { Trk.toast(err.message, 'error'); }).then(function () { btn.disabled = false; });
    }
  });

  /* OTP modal */
  var modal = $('trk-otp-modal'), otpInput = $('trk-otp-input'), otpErr = $('trk-otp-error');
  function openOtp() { otpInput.value = ''; otpErr.textContent = ''; modal.classList.add('open'); setTimeout(function () { otpInput.focus(); }, 50); }
  function closeOtp() { modal.classList.remove('open'); }
  $('trk-otp-cancel').addEventListener('click', closeOtp);
  modal.addEventListener('click', function (e) { if (e.target === modal) closeOtp(); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeOtp(); });
  otpInput.addEventListener('input', function () { otpInput.value = otpInput.value.replace(/\D/g, '').slice(0, 6); });
  $('trk-otp-form').addEventListener('submit', function (e) {
    e.preventDefault();
    if (!/^\d{6}$/.test(otpInput.value)) { otpErr.textContent = 'Enter the 6-digit code from the rider\'s screen.'; return; }
    var btn = $('trk-otp-submit');
    btn.disabled = true; otpErr.textContent = '';
    rideAction('/driver/ride/verify-otp/', { ride_id: state.ride.id, otp: otpInput.value }, 'Passenger verified. Ride started — head to the destination.')
      .then(closeOtp)
      .catch(function (err) {
        otpErr.textContent = err.message;
        otpInput.select();
      })
      .then(function () { btn.disabled = false; });
  });

  /* ---------------------------------------------------------- rendering */
  function renderCoords() {
    var f = state.fix;
    $('trk-coords').textContent = f ? f.latitude.toFixed(5) + ', ' + f.longitude.toFixed(5) : '—';
    $('trk-accuracy').textContent = f && f.accuracy != null ? '±' + f.accuracy + ' m' : '—';
    $('trk-speed').textContent = f && f.speed != null ? Math.round(f.speed) + ' km/h' : '—';
  }

  function chip(el, cls, icon, text) {
    el.className = 'trk-chip ' + cls;
    el.innerHTML = (icon === 'pulse' ? '<span class="trk-pulse"></span>' : '<i class="bx ' + icon + '"></i>') + esc(text);
  }

  function renderStatus() {
    var g = $('trk-gps-chip'), n = $('trk-net-chip'), banner = $('trk-gps-banner');
    var gpsText = {
      idle: ['', 'bx-map-pin', 'Location off'], waiting: ['warn', 'bx-loader-alt bx-spin', 'Finding GPS…'],
      ok: ['ok', 'pulse', 'GPS live'], weak: ['warn', 'bx-error', 'GPS signal weak'],
      denied: ['bad', 'bx-block', 'Location blocked'], unavailable: ['bad', 'bx-error-circle', 'GPS unavailable'],
      unsupported: ['bad', 'bx-error-circle', 'No GPS on this device'],
    }[state.online ? state.gps : 'idle'];
    chip(g, gpsText[0], gpsText[1], state.online ? gpsText[2] : 'Offline — not sharing');

    if (!state.online) n.classList.add('trk-hidden');
    else {
      n.classList.remove('trk-hidden');
      if (state.net === 'ok') chip(n, state.lastSentAt ? 'ok' : 'info', 'bx-cloud-upload',
        state.lastSentAt ? 'Updated ' + Trk.ago((Date.now() - state.lastSentAt) / 1000) : 'Connecting…');
      else chip(n, 'bad', 'bx-wifi-off', state.net === 'offline' ? 'No internet — retrying' : 'Server unreachable — retrying');
    }
    $('trk-updated').textContent = state.lastSentAt ? new Date(state.lastSentAt).toLocaleTimeString() : '—';

    var msg = '';
    if (state.online && state.gps === 'denied') msg = 'Location access is blocked. Allow location for this site in your browser settings (the lock icon in the address bar), then reload.';
    else if (state.online && state.gps === 'unavailable') msg = 'Your device can\'t get a GPS fix. Move to an open area or turn on high-accuracy location.';
    else if (state.online && state.gps === 'unsupported') msg = 'This browser doesn\'t support location. Use the Turbo Driver app or another browser.';
    else if (state.online && document.visibilityState === 'hidden') msg = 'Keep this page open — browsers pause GPS in the background.';
    banner.classList.toggle('trk-hidden', !msg);
    banner.querySelector('span').textContent = msg;
  }

  var STEP_INDEX = { ACCEPTED: 0, ARRIVED: 1, IN_PROGRESS: 2, COMPLETED: 3 };

  function renderRide() {
    var box = $('trk-ride'), tr = state.tracking, r = state.ride;
    var statusChip = $('trk-driver-status');
    if (!r || !tr) {
      box.innerHTML = '<div class="trk-card"><h2>No active ride</h2><p class="trk-muted">' +
        (state.online ? 'You\'re online. Accept a request on the <a href="' + cfg.dashboard_url + '" style="color:#60a5fa">dashboard</a> and it will show up here.'
          : 'Go online to receive rides and share your location.') + '</p></div>';
      statusChip.textContent = state.online ? 'Online' : 'Offline';
      if (map) { ['pickup', 'drop'].forEach(function (k) { map.removeMarker(k); }); ['route', 'trip'].forEach(function (k) { map.removeRoute(k); }); }
      state.fittedFor = null;
      return;
    }
    statusChip.textContent = tr.stage === 'pickup' ? (tr.status === 'ARRIVED' ? 'Arrived at pickup' : 'On the way to pickup')
      : 'On the way to destination';
    var step = STEP_INDEX[tr.status] || 0;
    var steps = ['Assigned', 'Arrived', 'Started', 'Done'].map(function (t, i) {
      return '<div class="trk-step ' + (i < step ? 'done' : i === step ? 'now' : '') + '">' + t + '</div>';
    }).join('');
    var target = tr.stage === 'pickup' ? tr.pickup : tr.drop;
    var nav = target ? Trk.esc(TurboMap.navigateUrl(state.fix && { lat: state.fix.latitude, lng: state.fix.longitude }, target)) : '';
    var actions = '';
    var g = tr.geofence || {};
    var lockText = function (place) {
      if (g.reason === 'imprecise') return 'GPS not precise enough (±' + Math.round(g.accuracy_m || 0) + ' m)';
      if (g.reason === 'stale' || g.reason === 'no_gps') return 'Waiting for a fresh GPS fix';
      return (g.distance_m != null ? Trk.km(g.distance_m / 1000) + ' away · ' : '') + 'unlocks within ' + (g.radius_m || 50) + ' m of the ' + place;
    };
    if (tr.status === 'ACCEPTED') {
      actions = g.within
        ? '<button class="trk-btn primary block" data-act="arrived"><i class="bx bx-flag"></i>I\'ve arrived</button>'
        : '<button class="trk-btn ghost block" disabled><i class="bx bx-lock-alt"></i>I\'ve arrived — ' + esc(lockText('pickup')) + '</button>';
    } else if (tr.status === 'ARRIVED') {
      actions = '<button class="trk-btn primary block" data-act="otp"><i class="bx bx-key"></i>Verify passenger OTP</button>';
    } else if (tr.status === 'IN_PROGRESS') {
      actions = g.within
        ? '<button class="trk-btn success block" data-act="complete"><i class="bx bx-check-circle"></i>Complete ride</button>'
        : '<button class="trk-btn ghost block" disabled><i class="bx bx-lock-alt"></i>Complete — ' + esc(lockText('destination')) + '</button>';
    }
    var hint = g.within && tr.status === 'ACCEPTED'
      ? '<div class="trk-banner info"><i class="bx bx-map-pin"></i><span>You\'re at the pickup. Tap "I\'ve arrived", then ask the rider for their OTP.</span></div>'
      : g.within && tr.status === 'IN_PROGRESS'
        ? '<div class="trk-banner info"><i class="bx bx-flag"></i><span>You\'ve reached the destination. Tap "Complete ride".</span></div>' : '';
    var dist = tr.stage === 'pickup' ? tr.distance_to_pickup_km : tr.distance_to_destination_km;

    box.innerHTML =
      '<div class="trk-stage"><strong>' + esc(tr.stage_label) + '</strong><span class="trk-small">Ride #' + r.id + ' · ' + esc(r.car_type_display) +
        ' · ₹' + Number(r.fare || 0).toFixed(2) + ' · paid after the ride</span></div>' +
      '<div class="trk-steps">' + steps + '</div>' + hint +
      '<div class="trk-metrics">' +
        '<div class="trk-metric"><span>' + (tr.stage === 'pickup' ? 'To pickup' : 'To drop') + '</span><strong>' + Trk.km(dist) + '</strong></div>' +
        '<div class="trk-metric"><span>ETA</span><strong>' + (tr.eta_minutes == null ? '—' : tr.eta_minutes === 0 ? 'Here' : tr.eta_minutes + ' min') + '</strong></div>' +
        '<div class="trk-metric"><span>Trip</span><strong>' + Trk.km(tr.trip_route && tr.trip_route.distance_km) + '</strong></div>' +
      '</div>' +
      '<div class="trk-card"><div class="trk-person"><div class="trk-avatar">' + esc((state.rider && state.rider.full_name || '?').charAt(0)) + '</div>' +
        '<div class="trk-person-info"><strong>' + esc(state.rider && state.rider.full_name) + '</strong><span class="trk-small">Your passenger</span></div>' +
        (state.rider && state.rider.phone ? '<a class="trk-btn round" href="tel:' + esc(state.rider.phone) + '" aria-label="Call rider"><i class="bx bxs-phone"></i></a>' : '') +
      '</div>' +
      '<div class="trk-points"><div class="trk-point from"><span>Pickup</span>' + esc(tr.pickup && tr.pickup.label) + '</div>' +
        '<div class="trk-point to"><span>Drop</span>' + esc(tr.drop && tr.drop.label) + '</div></div>' +
      (nav ? '<a class="trk-btn ghost block" target="_blank" rel="noopener" href="' + nav + '"><i class="bx bx-navigation"></i>Navigate in Google Maps</a>' : '') +
      '</div>' + actions;
    drawTrip();
  }

  /* ---------------------------------------------------------- map */
  function drawMe(animate) {
    if (!map || !state.fix) return;
    var p = { lat: state.fix.latitude, lng: state.fix.longitude };
    map.setMarker('me', p, { kind: 'car', heading: state.fix.heading, title: 'You', animateMs: animate ? 2500 : 0 });
    if (state.follow && !state.tracking) map.panTo(p);
    if (!state.firstFixShown) { state.firstFixShown = true; map.fit([p]); }
  }

  function drawTrip() {
    if (!map) return;
    var tr = state.tracking;
    if (!tr) return;
    if (tr.pickup) map.setMarker('pickup', tr.pickup, { kind: 'pickup', label: 'P', title: 'Pickup' });
    if (tr.drop) map.setMarker('drop', tr.drop, { kind: 'drop', label: 'D', title: 'Drop' });
    if (tr.route && tr.route.geometry) map.setRoute('route', tr.route.geometry, { color: '#3b82f6' });
    else map.removeRoute('route');
    if (tr.stage === 'pickup' && tr.trip_route) map.setRoute('trip', tr.trip_route.geometry, { color: '#94a3b8', dashed: true });
    else map.removeRoute('trip');
    var key = tr.ride_id + ':' + tr.stage;
    if (state.fittedFor !== key) {
      state.fittedFor = key;
      var me = state.fix && { lat: state.fix.latitude, lng: state.fix.longitude };
      map.fit([me, tr.stage === 'pickup' ? tr.pickup : tr.drop, tr.stage === 'pickup' ? null : tr.pickup]);
    }
  }

  $('trk-recenter').addEventListener('click', function () {
    state.follow = true;
    var me = state.fix && { lat: state.fix.latitude, lng: state.fix.longitude };
    var tr = state.tracking;
    if (map) map.fit([me, tr && (tr.stage === 'pickup' ? tr.pickup : tr.drop)]);
  });

  /* ---------------------------------------------------------- lifecycle */
  window.addEventListener('online', function () { state.net = 'ok'; if (state.loop) state.loop.now(); });
  window.addEventListener('offline', function () { state.net = 'offline'; renderStatus(); });
  document.addEventListener('visibilitychange', function () {
    renderStatus();
    if (document.visibilityState === 'visible' && state.online) { keepAwake(); if (state.loop) state.loop.now(); }
  });
  setInterval(renderStatus, 1000); // keep "updated x s ago" fresh

  TurboMap.create($('trk-map'), cfg.maps).then(function (m) {
    map = m;
    map.onUserMove(function () { state.follow = false; });
    drawMe(false);
    drawTrip();
  }).catch(function () { $('trk-map').innerHTML = '<p style="padding:20px">The map could not be loaded.</p>'; });

  setOnlineUi(state.online);
  applyActiveRide(cfg.initial || { ride: null, tracking: null });
  if (state.online) startTracking();
  else { renderStatus(); state.loop = null; }
})();
