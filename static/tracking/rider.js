/* Rider live tracking page: polls /api/rider/ride/tracking/ every 3 s (never overlapping),
 * glides the assigned driver's car on the map, shows distance/ETA, and the pickup OTP. */
(function () {
  'use strict';
  var cfg = JSON.parse(document.getElementById('trk-config').textContent);
  var $ = function (id) { return document.getElementById(id); };
  var api = Trk.api, esc = Trk.esc;
  var q = '?ride_id=' + cfg.ride_id;

  var state = { data: null, otp: null, otpFor: null, otpFetchedAt: 0, fittedFor: null, follow: true, loop: null,
                net: 'ok', lastOkAt: 0, driverKey: null };
  var map = null;

  /* ---------------------------------------------------------- polling */
  function tick() {
    return api('/rider/ride/tracking/' + q).then(function (d) {
      state.net = 'ok'; state.lastOkAt = Date.now();
      var statusChanged = !state.data || state.data.status !== d.status;
      state.data = d;
      render(statusChanged);
      if (d.status === 'COMPLETED' || d.status === 'CANCELLED') state.loop && state.loop.stop();
      return maybeFetchOtp(statusChanged);
    }).catch(function (e) {
      if (e.status === 401 || e.status === 403) window.location.href = cfg.login_url;
      else if (e.status === 404) { state.loop && state.loop.stop(); $('trk-stage').innerHTML = '<strong>Ride not found</strong>'; }
      else state.net = navigator.onLine ? 'error' : 'offline';
      renderConn();
    });
  }

  function needsOtp(d) { return d && (d.status === 'ACCEPTED' || d.status === 'ARRIVED') && !d.otp_verified; }

  function maybeFetchOtp(statusChanged) {
    var d = state.data;
    if (!needsOtp(d)) { state.otp = null; renderOtp(); return; }
    var expired = state.otp && state.otp.expires_at && new Date(state.otp.expires_at) <= new Date();
    if (statusChanged || !state.otp || expired || Date.now() - state.otpFetchedAt > 30000) {
      return api('/rider/ride/otp/' + q).then(function (o) {
        state.otp = o; state.otpFetchedAt = Date.now(); renderOtp();
      }).catch(function () {});
    }
  }

  /* ---------------------------------------------------------- rendering */
  var STEP_INDEX = { CONFIRMED: -1, PENDING: -1, ACCEPTED: 0, ARRIVED: 1, IN_PROGRESS: 2, COMPLETED: 3 };

  function render(statusChanged) {
    var d = state.data;
    var stage = $('trk-stage');
    stage.className = 'trk-stage' + (d.status === 'COMPLETED' ? ' done' : d.status === 'CANCELLED' ? ' cancel' : '');
    var sub = d.status === 'ACCEPTED' && d.eta_minutes != null ? 'Arriving in about ' + d.eta_minutes + ' min (' + Trk.clock(d.eta_at) + ')'
      : d.status === 'IN_PROGRESS' && d.eta_minutes != null ? 'Expected at destination ' + Trk.clock(d.eta_at)
      : d.status === 'ARRIVED' ? 'Your driver is waiting at the pickup point'
      : 'Ride #' + d.ride_id;
    stage.innerHTML = '<strong>' + esc(d.stage_label) + '</strong><span class="trk-small">' + esc(sub) + '</span>';

    var step = STEP_INDEX[d.status];
    $('trk-steps').innerHTML = ['Assigned', 'Arrived', 'Started', 'Arrived at drop'].map(function (t, i) {
      return '<div class="trk-step ' + (step > i ? 'done' : step === i ? 'now' : '') + '">' + t + '</div>';
    }).join('');
    $('trk-steps').classList.toggle('trk-hidden', step === undefined || step < 0 || d.status === 'CANCELLED');

    $('trk-searching').classList.toggle('trk-hidden', d.status !== 'CONFIRMED');
    $('trk-pay').classList.toggle('trk-hidden', d.status !== 'PENDING');

    // metrics
    var showMetrics = d.status === 'ACCEPTED' || d.status === 'ARRIVED' || d.status === 'IN_PROGRESS';
    $('trk-metrics').classList.toggle('trk-hidden', !showMetrics);
    if (showMetrics) {
      $('m-pickup').textContent = d.status === 'IN_PROGRESS' ? 'Picked up' : d.status === 'ARRIVED' ? 'Here' : Trk.km(d.distance_to_pickup_km);
      $('m-drop').textContent = Trk.km(d.distance_to_destination_km);
      $('m-eta').textContent = d.eta_minutes == null ? '—' : d.status === 'ARRIVED' ? 'Now' : d.eta_minutes + ' min';
    }

    renderDriver(d.driver);
    $('trk-points').innerHTML = '<div class="trk-point from"><span>Pickup</span>' + esc(d.pickup && d.pickup.label) + '</div>' +
      '<div class="trk-point to"><span>Drop</span>' + esc(d.drop && d.drop.label) + '</div>';
    $('trk-done').classList.toggle('trk-hidden', d.status !== 'COMPLETED');
    if (d.status === 'COMPLETED') renderDone();
    renderConn();
    drawMap(statusChanged);
  }

  function renderDriver(dr) {
    var box = $('trk-driver');
    if (!dr) { box.classList.add('trk-hidden'); return; }
    box.classList.remove('trk-hidden');
    var key = JSON.stringify(dr);
    if (state.driverKey === key) return;  // avoid flicker: re-render only when details change
    state.driverKey = key;
    var avatar = dr.photo ? '<img class="trk-avatar" src="' + esc(dr.photo) + '" alt="">' : '<div class="trk-avatar">' + esc(dr.full_name.charAt(0)) + '</div>';
    box.innerHTML = '<div class="trk-person">' + avatar +
      '<div class="trk-person-info"><strong>' + esc(dr.full_name) + '</strong>' +
      '<span class="trk-small">' + esc([dr.vehicle_model, dr.vehicle_type].filter(Boolean).join(' · ') || 'Vehicle details not added') + '</span>' +
      '<span class="trk-row" style="gap:8px">' + (dr.vehicle_number ? '<span class="trk-plate">' + esc(dr.vehicle_number) + '</span>' : '') +
      (dr.rating ? '<span class="trk-rating">★ ' + dr.rating + '</span>' : '') + '</span></div>' +
      (dr.phone ? '<a class="trk-btn round" href="tel:' + esc(dr.phone) + '" aria-label="Call driver"><i class="bx bxs-phone"></i></a>' : '') +
      '</div>';
  }

  function renderConn() {
    var d = state.data, c = $('trk-conn');
    if (!d || !(d.status === 'ACCEPTED' || d.status === 'ARRIVED' || d.status === 'IN_PROGRESS')) { c.classList.add('trk-hidden'); return; }
    c.classList.remove('trk-hidden');
    var loc = d.driver_location;
    if (state.net !== 'ok') { c.className = 'trk-chip bad'; c.innerHTML = '<i class="bx bx-wifi-off"></i>Reconnecting…'; }
    else if (!loc) { c.className = 'trk-chip warn'; c.innerHTML = '<i class="bx bx-error"></i>Waiting for driver\'s GPS'; }
    else if (loc.is_stale) { c.className = 'trk-chip warn'; c.innerHTML = '<i class="bx bx-error"></i>Driver GPS signal lost · ' + esc(Trk.ago(loc.age_seconds)); }
    else { c.className = 'trk-chip ok'; c.innerHTML = '<span class="trk-pulse"></span>Live · updated ' + esc(Trk.ago(loc.age_seconds)); }
  }

  var otpTimer = null;
  function renderOtp() {
    var box = $('trk-otp'), o = state.otp;
    clearInterval(otpTimer);
    if (!o || !needsOtp(state.data)) { box.classList.add('trk-hidden'); return; }
    box.classList.remove('trk-hidden');
    var codeEl = $('trk-otp-code'), note = $('trk-otp-note'), regen = $('trk-otp-regen');
    function paint() {
      var left = Math.round((new Date(o.expires_at) - new Date()) / 1000);
      var expired = o.is_expired || left <= 0;
      codeEl.textContent = expired ? '••••••' : o.otp;
      codeEl.classList.toggle('expired', expired);
      if (o.is_locked) note.textContent = 'Too many wrong attempts. Get a new code to try again.';
      else if (expired) note.textContent = 'This code has expired.';
      else note.textContent = 'Share this code with your driver only after you get in. Expires in ' +
        Math.floor(left / 60) + ':' + String(left % 60).padStart(2, '0') + '.';
      regen.classList.toggle('primary', expired || o.is_locked);
      regen.classList.toggle('ghost', !(expired || o.is_locked));
    }
    paint();
    otpTimer = setInterval(paint, 1000);
  }

  $('trk-otp-regen').addEventListener('click', function () {
    var btn = this;
    btn.disabled = true;
    api('/rider/ride/otp/regenerate/', { method: 'POST', body: { ride_id: cfg.ride_id } })
      .then(function (o) { state.otp = o; state.otpFetchedAt = Date.now(); renderOtp(); Trk.toast('New code ready. The old one no longer works.', 'success'); })
      .catch(function (e) { Trk.toast(e.message, 'error'); })
      .then(function () { btn.disabled = false; });
  });

  function renderDone() {
    var d = state.data;
    $('trk-done-fare').textContent = d.fare != null ? '₹' + Number(d.fare).toFixed(2) : '';
    $('trk-done-pay').textContent = d.payment_method_display ? 'Paid by ' + d.payment_method_display : '';
    var stars = $('trk-stars');
    if (d.rating) { stars.innerHTML = '<span class="trk-rating" style="font-size:1.1rem">You rated ' + d.rating + ' ★</span>'; return; }
    if (stars.dataset.ready) return;
    stars.dataset.ready = '1';
    stars.innerHTML = [1, 2, 3, 4, 5].map(function (n) { return '<button type="button" data-n="' + n + '" aria-label="' + n + ' stars">★</button>'; }).join('');
    stars.addEventListener('click', function (e) {
      var b = e.target.closest('button');
      if (!b) return;
      api('/rider/rides/' + cfg.ride_id + '/rate/', { method: 'POST', body: { rating: +b.dataset.n } })
        .then(function () { d.rating = +b.dataset.n; renderDone(); Trk.toast('Thanks for rating your driver!', 'success'); })
        .catch(function (err) { Trk.toast(err.message, 'error'); });
    });
  }

  /* ---------------------------------------------------------- map */
  function drawMap(statusChanged) {
    var d = state.data;
    if (!map || !d) return;
    if (d.pickup) map.setMarker('pickup', d.pickup, { kind: 'pickup', label: 'P', title: 'Pickup' });
    if (d.drop) map.setMarker('drop', d.drop, { kind: 'drop', label: 'D', title: 'Drop' });
    var loc = d.driver_location;
    if (loc) map.setMarker('driver', loc, { kind: 'car', heading: loc.heading, title: d.driver ? d.driver.full_name : 'Driver' });
    else map.removeMarker('driver');

    if (d.route && d.route.geometry) map.setRoute('route', d.route.geometry, { color: '#3b82f6' }); else map.removeRoute('route');
    if (d.trip_route && d.stage === 'pickup') map.setRoute('trip', d.trip_route.geometry, { color: '#94a3b8', dashed: true });
    else if (!d.route && d.trip_route) map.setRoute('trip', d.trip_route.geometry, { color: '#94a3b8', dashed: true });
    else map.removeRoute('trip');

    var key = d.status + ':' + (loc ? 1 : 0);
    if (statusChanged || state.fittedFor !== key) {
      state.fittedFor = key; state.follow = true;
      map.fit(d.stage === 'destination' ? [loc, d.drop] : [loc, d.pickup, loc ? null : d.drop]);
    } else if (loc && state.follow && !map.contains(loc)) {
      map.panTo(loc);   // keep the moving car in view
    }
  }

  $('trk-recenter').addEventListener('click', function () {
    var d = state.data;
    state.follow = true;
    if (map && d) map.fit(d.stage === 'destination' ? [d.driver_location, d.drop] : [d.driver_location, d.pickup]);
  });

  /* ---------------------------------------------------------- start */
  window.addEventListener('online', function () { if (state.loop) state.loop.now(); });
  document.addEventListener('visibilitychange', function () { if (document.visibilityState === 'visible' && state.loop) state.loop.now(); });
  setInterval(renderConn, 1000);

  TurboMap.create($('trk-map'), cfg.maps).then(function (m) {
    map = m;
    map.onUserMove(function () { state.follow = false; });
    if (state.data) drawMap(true);
  }).catch(function () { $('trk-map').innerHTML = '<p style="padding:20px">The map could not be loaded.</p>'; });

  if (cfg.initial) { state.data = cfg.initial; render(true); maybeFetchOtp(true); }
  state.loop = Trk.loop(tick, 3000);
})();
