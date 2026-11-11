import 'dart:async';

import 'package:flutter/material.dart';
import 'package:turbo_core/turbo_core.dart';
import 'package:url_launcher/url_launcher.dart';

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
  List<Choice> _availability = const [];
  String? _error;
  bool _loading = true;
  int? _busyRide;
  Timer? _poll;

  ApiClient get _api => AuthScope.read(context).api;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
    _poll = Timer.periodic(const Duration(seconds: 10), (_) => _load(quiet: true));
  }

  @override
  void dispose() {
    _poll?.cancel();
    super.dispose();
  }

  Future<void> _load({bool quiet = false}) async {
    try {
      final auth = AuthScope.read(context);
      final results = await Future.wait([
        _api.get('/driver/profile/'),
        _api.get('/driver/rides/ongoing/'),
        _api.get('/driver/rides/available/'),
        auth.meta(),
      ]);
      if (!mounted) return;
      setState(() {
        _profile = DriverProfile.fromJson(results[0] as Map<String, dynamic>);
        _ongoing = PageOf.fromJson(results[1], Ride.fromJson).results;
        _available = PageOf.fromJson(results[2], Ride.fromJson).results;
        _availability = (results[3] as Meta).availability;
        _error = null;
      });
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
                if (_profile != null && (_profile!.licenseNumber.isEmpty || _profile!.vehicleInfo.isEmpty))
                  const Card(
                    child: ListTile(
                      leading: Icon(Icons.info_outline),
                      title: Text('Add your licence and vehicle details in Profile so riders know what to look for.'),
                    ),
                  ),
                _Header('Ongoing rides', _ongoing.length),
                if (_ongoing.isEmpty) const EmptyState('No ongoing rides.', icon: Icons.directions_car_outlined),
                for (final r in _ongoing)
                  _RideCard(
                    ride: r,
                    busy: _busyRide == r.id,
                    onCall: (r.rider.phone ?? '').isNotEmpty ? () => _call(r.rider.phone!) : null,
                    actions: [
                      FilledButton.icon(
                        onPressed: _busyRide == null ? () => _rideAction(r, 'complete', 'Ride completed. Earnings updated.') : null,
                        icon: const Icon(Icons.flag),
                        label: const Text('Complete'),
                      ),
                    ],
                  ),
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
                      const SizedBox(width: 8),
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
                  : Row(mainAxisAlignment: MainAxisAlignment.end, children: actions),
            ]),
          ),
        ),
      );
}
