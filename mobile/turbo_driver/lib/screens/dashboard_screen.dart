import 'dart:async';

import 'package:flutter/material.dart';
import 'package:turbo_core/turbo_core.dart';
import 'package:url_launcher/url_launcher.dart';

import '../location_service.dart';

/// Ongoing rides + new requests, refreshed every 10 seconds.
class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  DriverProfile? _profile;
  List<Ride> _ongoing = const [];
  List<Ride> _available = const [];
  List<Ride> _unpaid = const [];
  List<Choice> _availability = const [];
  String? _error;
  bool _loading = true;
  int? _busyRide;
  Timer? _poll;
  DriverLocationService? _location;

  ApiClient get _api => AuthScope.read(context).api;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _location = DriverLocationService(_api)
        ..addListener(_onLocation)
        ..onTripChanged = (() => _load(quiet: true))
        ..onStoppedByServer = ((msg) {
          if (mounted) showSnack(context, msg, error: true);
          _load(quiet: true);
        });
      _load();
    });
    _poll = Timer.periodic(const Duration(seconds: 10), (_) => _load(quiet: true));
  }

  void _onLocation() {
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    _poll?.cancel();
    _location?.removeListener(_onLocation);
    _location?.dispose();
    super.dispose();
  }

  // 50 m rule (checked again by the server): unlock when the latest fix is close enough.
  bool _within(Ride r) => _location?.tracking?.rideId == r.id && (_location?.tracking?.withinRadius ?? false);
  String _lock(Ride r, String place) =>
      _location?.tracking?.rideId == r.id ? _location!.tracking!.lockText(place) : 'waiting for GPS';

  Future<void> _collectCash(Ride ride) async {
    if (!await confirmDialog(context, 'Cash collected?', 'Did you receive ${money(ride.fare)} in cash?', action: 'Yes')) return;
    setState(() => _busyRide = ride.id);
    try {
      await _api.post('/driver/rides/${ride.id}/cash-collected/');
      if (mounted) showSnack(context, 'Cash payment recorded.');
    } catch (e) {
      if (mounted) showSnack(context, errorText(e), error: true);
    } finally {
      await _load(quiet: true);
      if (mounted) setState(() => _busyRide = null);
    }
  }

  /// Share GPS whenever the driver is online; stop when offline.
  void _syncTracking() {
    final loc = _location;
    if (loc == null || _profile == null) return;
    final online = _profile!.availability != 'offline';
    if (online && !loc.running && loc.gps != GpsState.denied && loc.gps != GpsState.serviceOff) loc.start();
    if (!online && loc.running) loc.stop();
  }

  Future<void> _statusAction(Ride ride, String status, String done) async {
    setState(() => _busyRide = ride.id);
    try {
      await _api.post('/driver/ride/status/', {'ride_id': ride.id, 'status': status});
      if (mounted) showSnack(context, done);
    } catch (e) {
      if (mounted) showSnack(context, errorText(e), error: true);
    } finally {
      await _load(quiet: true);
      if (mounted) setState(() => _busyRide = null);
    }
  }

  Future<void> _verifyOtp(Ride ride) async {
    final ok = await showDialog<bool>(context: context, builder: (_) => _OtpDialog(api: _api, rideId: ride.id));
    if (ok == true && mounted) {
      showSnack(context, 'Passenger verified. Ride started — head to the destination.');
      await _load(quiet: true);
    }
  }

  Future<void> _load({bool quiet = false}) async {
    try {
      final auth = AuthScope.read(context);
      final results = await Future.wait([
        _api.get('/driver/profile/'),
        _api.get('/driver/rides/ongoing/'),
        _api.get('/driver/rides/available/'),
        auth.meta(),
        _api.get('/driver/rides/unpaid/'),
      ]);
      if (!mounted) return;
      setState(() {
        _profile = DriverProfile.fromJson(results[0] as Map<String, dynamic>);
        _ongoing = PageOf.fromJson(results[1], Ride.fromJson).results;
        _available = PageOf.fromJson(results[2], Ride.fromJson).results;
        _availability = (results[3] as Meta).availability;
        _unpaid = PageOf.fromJson(results[4], Ride.fromJson).results;
        _error = null;
      });
      _syncTracking();
    } catch (e) {
      if (mounted && !quiet) setState(() => _error = errorText(e));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _rideAction(Ride ride, String action, String done) async {
    setState(() => _busyRide = ride.id);
    try {
      await _api.post('/driver/rides/${ride.id}/$action/');
      if (mounted) showSnack(context, done);
      await _load(quiet: true);
    } catch (e) {
      if (mounted) showSnack(context, errorText(e), error: true);
      await _load(quiet: true);
    } finally {
      if (mounted) setState(() => _busyRide = null);
    }
  }

  Future<void> _setAvailability(String value) async {
    try {
      final json = await _api.patch('/driver/profile/', {'availability_status': value});
      if (mounted) setState(() => _profile = DriverProfile.fromJson(json as Map<String, dynamic>));
      _syncTracking();
    } catch (e) {
      if (mounted) showSnack(context, errorText(e), error: true);
    }
  }

  Future<void> _call(String phone) async {
    try {
      await launchUrl(Uri(scheme: 'tel', path: phone));
    } catch (_) {
      if (mounted) showSnack(context, 'Could not start a call to $phone', error: true);
    }
  }

  @override
  Widget build(BuildContext context) {
    final offline = _profile?.availability == 'offline';
    return Scaffold(
      appBar: AppBar(
        title: const Text('Rides'),
        actions: [
          if (_profile != null && _availability.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(right: 12),
              child: DropdownButton<String>(
                value: _profile!.availability,
                underline: const SizedBox.shrink(),
                items: [
                  for (final a in _availability)
                    DropdownMenuItem(
                      value: a.value,
                      child: Row(children: [
                        Icon(Icons.circle, size: 10, color: _availabilityColor(a.value)),
                        const SizedBox(width: 6),
                        Text(a.label),
                      ]),
                    ),
                ],
                onChanged: (v) => v == null ? null : _setAvailability(v),
              ),
            ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _load,
              child: ListView(padding: const EdgeInsets.all(12), children: [
                ErrorBanner(_error, onRetry: _load),
                if (_location != null) _GpsBanner(service: _location!, online: !offline),
                if (_profile != null && (_profile!.licenseNumber.isEmpty || _profile!.vehicleInfo.isEmpty))
                  const Card(
                    child: ListTile(
                      leading: Icon(Icons.info_outline),
                      title: Text('Add your licence and vehicle details in Profile so riders know what to look for.'),
                    ),
                  ),
                _Header('Ongoing rides', _ongoing.length),
                if (_ongoing.isEmpty) const EmptyState('No ongoing rides.', icon: Icons.directions_car_outlined),
                for (final r in _ongoing) ...[
                  _RideCard(
                    ride: r,
                    busy: _busyRide == r.id,
                    onCall: (r.rider.phone ?? '').isNotEmpty ? () => _call(r.rider.phone!) : null,
                    actions: [
                      StatusChip(r.status, r.statusDisplay),
                      if (r.status == 'ACCEPTED')
                        FilledButton.icon(
                          onPressed: _busyRide == null && _within(r)
                              ? () => _statusAction(r, 'ARRIVED', 'Marked as arrived. Ask the rider for their OTP.')
                              : null,
                          icon: Icon(_within(r) ? Icons.flag : Icons.lock_outline),
                          label: Text(_within(r) ? "I've arrived" : "I've arrived · ${_lock(r, 'pickup')}"),
                        ),
                      if (r.status == 'ARRIVED')
                        FilledButton.icon(
                          onPressed: _busyRide == null ? () => _verifyOtp(r) : null,
                          icon: const Icon(Icons.key),
                          label: const Text('Verify OTP'),
                        ),
                      if (r.status == 'IN_PROGRESS')
                        FilledButton.icon(
                          onPressed: _busyRide == null && _within(r)
                              ? () => _statusAction(r, 'COMPLETED', 'Ride completed. The rider now pays by UPI or cash.')
                              : null,
                          icon: Icon(_within(r) ? Icons.flag : Icons.lock_outline),
                          label: Text(_within(r) ? 'Complete ride' : 'Complete · ${_lock(r, 'destination')}'),
                        ),
                    ],
                  ),
                  if (_location?.tracking?.rideId == r.id) ...[
                    TripMetrics(_location!.tracking!),
                    const SizedBox(height: 6),
                    TripMap(
                      tracking: _location!.tracking,
                      me: _location!.latLng,
                      meHeading: _location!.position?.heading,
                      height: 280,
                      userAgent: 'com.turbocab.turbo_driver',
                    ),
                    const SizedBox(height: 6),
                    if (_location!.tracking!.target != null)
                      OutlinedButton.icon(
                        onPressed: () => launchUrl(
                          Uri.parse('https://www.google.com/maps/dir/?api=1&travelmode=driving'
                              '&destination=${_location!.tracking!.target!.latitude},${_location!.tracking!.target!.longitude}'),
                          mode: LaunchMode.externalApplication,
                        ),
                        icon: const Icon(Icons.navigation),
                        label: const Text('Navigate in Google Maps'),
                      ),
                    const SizedBox(height: 8),
                  ],
                ],
                if (_unpaid.isNotEmpty) ...[
                  const SizedBox(height: 12),
                  _Header('Awaiting payment', _unpaid.length),
                  for (final r in _unpaid)
                    _RideCard(
                      ride: r,
                      busy: _busyRide == r.id,
                      actions: [
                        Text(r.paymentStatus == 'CASH_DUE' ? 'Rider chose cash' : "Rider hasn't paid yet",
                            style: const TextStyle(color: Colors.white60)),
                        FilledButton.icon(
                          onPressed: _busyRide == null ? () => _collectCash(r) : null,
                          icon: const Icon(Icons.payments_outlined),
                          label: const Text('Cash collected'),
                        ),
                      ],
                    ),
                ],
                const SizedBox(height: 12),
                _Header('New requests', _available.length),
                if (offline)
                  const Card(child: ListTile(leading: Icon(Icons.power_settings_new), title: Text('You are offline. Switch to Available to accept rides.'))),
                if (_available.isEmpty) const EmptyState('No new ride requests. This list refreshes automatically.'),
                for (final r in _available)
                  _RideCard(
                    ride: r,
                    busy: _busyRide == r.id,
                    actions: [
                      OutlinedButton(
                        onPressed: _busyRide == null ? () => _rideAction(r, 'decline', 'Ride declined.') : null,
                        child: const Text('Decline'),
                      ),
                      FilledButton(
                        onPressed: _busyRide == null && !offline ? () => _rideAction(r, 'accept', 'Ride accepted! Head to the pickup.') : null,
                        child: const Text('Accept'),
                      ),
                    ],
                  ),
              ]),
            ),
    );
  }
}

Color _availabilityColor(String v) => switch (v) {
      'available' => Colors.green,
      'on-trip' => Colors.blue,
      _ => Colors.grey,
    };

class _Header extends StatelessWidget {
  const _Header(this.text, this.count);

  final String text;
  final int count;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Text('$text ($count)', style: Theme.of(context).textTheme.titleMedium),
      );
}

class _RideCard extends StatelessWidget {
  const _RideCard({required this.ride, required this.actions, required this.busy, this.onCall});

  final Ride ride;
  final List<Widget> actions;
  final bool busy;
  final VoidCallback? onCall;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: Card(
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                Expanded(child: Text(money(ride.fare), style: Theme.of(context).textTheme.titleLarge)),
                Text('${ride.distance.toStringAsFixed(1)} km · ${ride.carTypeDisplay}', style: const TextStyle(color: Colors.white60)),
              ]),
              const SizedBox(height: 10),
              Row(children: [
                const Icon(Icons.trip_origin, size: 18, color: Colors.green),
                const SizedBox(width: 8),
                Expanded(child: Text(ride.pickup, maxLines: 2, overflow: TextOverflow.ellipsis)),
              ]),
              const SizedBox(height: 6),
              Row(children: [
                const Icon(Icons.location_on, size: 18, color: Colors.redAccent),
                const SizedBox(width: 8),
                Expanded(child: Text(ride.drop, maxLines: 2, overflow: TextOverflow.ellipsis)),
              ]),
              const SizedBox(height: 8),
              Row(children: [
                const Icon(Icons.person_outline, size: 18, color: Colors.white54),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    '${ride.rider.fullName} · ${ride.paymentMethodDisplay ?? 'Unpaid'}',
                    style: const TextStyle(color: Colors.white70),
                  ),
                ),
                if (onCall != null) IconButton.filledTonal(onPressed: onCall, icon: const Icon(Icons.call), tooltip: 'Call rider'),
              ]),
              const SizedBox(height: 8),
              busy
                  ? const LinearProgressIndicator()
                  : Wrap(alignment: WrapAlignment.end, crossAxisAlignment: WrapCrossAlignment.center, spacing: 8, runSpacing: 8, children: actions),
            ]),
          ),
        ),
      );
}


class _GpsBanner extends StatelessWidget {
  const _GpsBanner({required this.service, required this.online});

  final DriverLocationService service;
  final bool online;

  @override
  Widget build(BuildContext context) {
    if (!online) {
      return const Card(child: ListTile(leading: Icon(Icons.location_off), title: Text('Offline — your location is not shared.')));
    }
    final (IconData icon, Color color, String text) = switch (service.gps) {
      GpsState.live => (Icons.gps_fixed, Colors.green, 'GPS live'),
      GpsState.waiting => (Icons.gps_not_fixed, Colors.amber, 'Finding GPS…'),
      GpsState.weak => (Icons.gps_not_fixed, Colors.amber, 'GPS signal weak'),
      GpsState.denied => (Icons.gps_off, Colors.redAccent, 'Location permission needed'),
      GpsState.serviceOff => (Icons.gps_off, Colors.redAccent, 'Location is turned off'),
      GpsState.off => (Icons.gps_off, Colors.white54, 'Location off'),
    };
    final sent = service.lastSentAt == null ? '' : ' · sent ${DateTime.now().difference(service.lastSentAt!).inSeconds}s ago';
    return Card(
      child: ListTile(
        leading: Icon(icon, color: color),
        title: Text(service.networkOk ? '$text$sent' : 'No connection — retrying', style: TextStyle(color: color)),
        subtitle: Text(service.error ??
            (service.position == null
                ? 'Your position is sent every 3 seconds while you are online.'
                : '${service.position!.latitude.toStringAsFixed(5)}, ${service.position!.longitude.toStringAsFixed(5)}'
                    ' · ±${service.position!.accuracy.round()} m')),
        trailing: service.gps == GpsState.denied || service.gps == GpsState.serviceOff
            ? TextButton(onPressed: service.start, child: const Text('Retry'))
            : null,
      ),
    );
  }
}

/// Enter the rider's 6-digit code. Pops `true` when the ride has started.
class _OtpDialog extends StatefulWidget {
  const _OtpDialog({required this.api, required this.rideId});

  final ApiClient api;
  final int rideId;

  @override
  State<_OtpDialog> createState() => _OtpDialogState();
}

class _OtpDialogState extends State<_OtpDialog> {
  final _code = TextEditingController();
  String? _error;
  bool _busy = false;

  @override
  void dispose() {
    _code.dispose();
    super.dispose();
  }

  Future<void> _verify() async {
    if (!RegExp(r'^\d{6}$').hasMatch(_code.text)) {
      setState(() => _error = "Enter the 6-digit code from the rider's screen.");
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await widget.api.post('/driver/ride/verify-otp/', {'ride_id': widget.rideId, 'otp': _code.text});
      if (mounted) Navigator.pop(context, true);
    } catch (e) {
      if (mounted) setState(() => _error = errorText(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
        title: const Text('Verify passenger OTP'),
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          const Text("Ask the rider for the 6-digit code shown on their screen."),
          const SizedBox(height: 16),
          TextField(
            controller: _code,
            autofocus: true,
            keyboardType: TextInputType.number,
            maxLength: 6,
            textAlign: TextAlign.center,
            autofillHints: const [AutofillHints.oneTimeCode],
            style: const TextStyle(fontSize: 30, fontWeight: FontWeight.w800, letterSpacing: 10),
            decoration: const InputDecoration(counterText: '', hintText: '••••••'),
            onSubmitted: (_) => _verify(),
          ),
          if (_error != null) Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
        ]),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          FilledButton(onPressed: _busy ? null : _verify, child: Text(_busy ? 'Verifying…' : 'Verify OTP')),
        ],
      );
}
