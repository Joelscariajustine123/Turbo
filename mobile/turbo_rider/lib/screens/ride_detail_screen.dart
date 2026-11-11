import 'dart:async';

import 'package:flutter/material.dart';
import 'package:turbo_core/turbo_core.dart';
import 'package:url_launcher/url_launcher.dart';

import '../geo.dart';

class RideDetailScreen extends StatefulWidget {
  const RideDetailScreen({super.key, required this.rideId, this.initial});

  final int rideId;
  final Ride? initial;

  @override
  State<RideDetailScreen> createState() => _RideDetailScreenState();
}

class _RideDetailScreenState extends State<RideDetailScreen> {
  Ride? _ride;
  String? _error;
  bool _busy = false;
  Timer? _poll;
  Timer? _trackTimer;
  bool _disposed = false;
  TripTracking? _trip;
  Map<String, dynamic>? _otp;
  DateTime? _otpFetchedAt;

  @override
  void initState() {
    super.initState();
    _ride = widget.initial;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _load();
      _trackLoop();
    });
    // Keep the status fresh while the ride is in progress.
    _poll = Timer.periodic(const Duration(seconds: 10), (_) {
      if (_ride?.isActive ?? true) _load(quiet: true);
    });
  }

  @override
  void dispose() {
    _disposed = true;
    _poll?.cancel();
    _trackTimer?.cancel();
    super.dispose();
  }

  /// Live driver position every 3 s during the trip. The next request starts only
  /// after the previous one finished, so slow networks never pile up requests.
  Future<void> _trackLoop() async {
    if (_disposed) return;
    final started = DateTime.now();
    final ride = _ride;
    if (ride != null && (ride.isTrip || ride.status == 'CONFIRMED')) {
      try {
        final api = AuthScope.read(context).api;
        final json = await api.get('/rider/ride/tracking/', query: {'ride_id': '${widget.rideId}'});
        final trip = TripTracking.fromJson(json as Map<String, dynamic>);
        final statusChanged = _trip?.status != trip.status;
        if (!_disposed) setState(() => _trip = trip);
        if (statusChanged && !_disposed) _load(quiet: true);
        await _maybeFetchOtp(trip, statusChanged);
      } catch (_) {
        // keep the last known position; retry on the next tick
      }
    }
    if (_disposed) return;
    final wait = const Duration(seconds: 3) - DateTime.now().difference(started);
    _trackTimer = Timer(wait.isNegative ? Duration.zero : wait, _trackLoop);
  }

  Future<void> _maybeFetchOtp(TripTracking trip, bool statusChanged) async {
    if (!trip.needsOtp) {
      if (_otp != null && !_disposed) setState(() => _otp = null);
      return;
    }
    final expires = DateTime.tryParse(str(_otp?['expires_at']));
    final stale = _otpFetchedAt == null || DateTime.now().difference(_otpFetchedAt!) > const Duration(seconds: 30);
    if (_otp == null || statusChanged || stale || (expires != null && expires.isBefore(DateTime.now()))) {
      try {
        final json = await AuthScope.read(context).api.get('/rider/ride/otp/', query: {'ride_id': '${widget.rideId}'});
        _otpFetchedAt = DateTime.now();
        if (!_disposed) setState(() => _otp = json as Map<String, dynamic>);
      } catch (_) {}
    }
  }

  Future<void> _newCode() async {
    try {
      final json = await AuthScope.read(context).api.post('/rider/ride/otp/regenerate/', {'ride_id': widget.rideId});
      _otpFetchedAt = DateTime.now();
      if (!mounted) return;
      setState(() => _otp = json as Map<String, dynamic>);
      showSnack(context, 'New code ready. The old one no longer works.');
    } catch (e) {
      if (mounted) showSnack(context, errorText(e), error: true);
    }
  }

  Future<void> _load({bool quiet = false}) async {
    try {
      final json = await AuthScope.read(context).api.get('/rider/rides/${widget.rideId}/');
      if (mounted) {
        setState(() {
          _ride = Ride.fromJson(json as Map<String, dynamic>);
          _error = null;
        });
      }
    } catch (e) {
      if (mounted && !quiet) setState(() => _error = errorText(e));
    }
  }

  Future<void> _action(String path, [Map<String, dynamic>? body, String? done]) async {
    setState(() => _busy = true);
    try {
      final json = await AuthScope.read(context).api.post('/rider/rides/${widget.rideId}/$path/', body);
      if (!mounted) return;
      setState(() => _ride = Ride.fromJson(json as Map<String, dynamic>));
      if (done != null) showSnack(context, done);
    } catch (e) {
      if (mounted) showSnack(context, errorText(e), error: true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _payUpi() async {
    final ride = _ride!;
    final meta = await AuthScope.read(context).meta();
    final link = Uri.parse(upiLink(meta.upiId, ride.fare, ride.id));
    var opened = false;
    try {
      opened = await launchUrl(link, mode: LaunchMode.externalApplication);
    } catch (_) {}
    if (!mounted) return;
    final txn = await showDialog<String>(
      context: context,
      builder: (_) => _TransactionDialog(upiId: meta.upiId, amount: ride.fare, openedApp: opened),
    );
    if (txn != null && txn.trim().isNotEmpty) {
      await _action('pay', {'payment_method': 'upi', 'transaction_id': txn.trim()}, 'Payment recorded. Finding you a driver…');
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
    final ride = _ride;
    return Scaffold(
      appBar: AppBar(title: Text('Ride #${widget.rideId}')),
      body: ride == null
          ? Center(child: _error != null ? ErrorBanner(_error, onRetry: _load) : const CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _load,
              child: ListView(padding: const EdgeInsets.all(16), children: [
                ErrorBanner(_error),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Row(children: [
                        Expanded(child: Text(money(ride.fare), style: Theme.of(context).textTheme.headlineMedium)),
                        StatusChip(ride.status, ride.statusDisplay),
                      ]),
                      const SizedBox(height: 12),
                      _line(Icons.trip_origin, Colors.green, ride.pickup),
                      const SizedBox(height: 8),
                      _line(Icons.location_on, Colors.redAccent, ride.drop),
                      const Divider(height: 24),
                      Text('${ride.carTypeDisplay} · ${ride.distance.toStringAsFixed(2)} km · ${formatWhen(ride.createdAt)}',
                          style: const TextStyle(color: Colors.white60)),
                      if (ride.paymentMethodDisplay != null)
                        Text('Paid by ${ride.paymentMethodDisplay}${ride.transactionId != null ? ' · ${ride.transactionId}' : ''}',
                            style: const TextStyle(color: Colors.white60)),
                    ]),
                  ),
                ),
                const SizedBox(height: 12),
                if (_otp != null && (_trip?.needsOtp ?? false)) ...[
                  _OtpCard(otp: _otp!, onNewCode: _newCode),
                  const SizedBox(height: 12),
                ],
                if (_trip != null && _trip!.isTrip) ...[
                  Row(children: [
                    Expanded(child: Text(_trip!.stageLabel, style: const TextStyle(fontWeight: FontWeight.w700))),
                    _LiveChip(trip: _trip!),
                  ]),
                  const SizedBox(height: 8),
                  TripMetrics(_trip!),
                  const SizedBox(height: 8),
                  TripMap(tracking: _trip, height: 300, userAgent: 'com.turbocab.turbo_rider'),
                  const SizedBox(height: 12),
                ],
                if (_trip?.status == 'CONFIRMED')
                  const Card(child: ListTile(
                    leading: SizedBox(width: 24, height: 24, child: CircularProgressIndicator(strokeWidth: 2)),
                    title: Text('Finding you a driver…'),
                    subtitle: Text('This screen updates automatically when a driver accepts.'),
                  )),
                if (ride.driver != null)
                  Card(
                    child: ListTile(
                      leading: CircleAvatar(
                        backgroundImage: ride.driver!.photo != null ? NetworkImage(ride.driver!.photo!) : null,
                        child: ride.driver!.photo == null ? const Icon(Icons.person) : null,
                      ),
                      title: Text(ride.driver!.fullName),
                      subtitle: Text([
                        if ((ride.driver!.vehicleInfo ?? '').isNotEmpty) ride.driver!.vehicleInfo!,
                        if ((ride.driver!.vehicleType ?? '').isNotEmpty) ride.driver!.vehicleType!,
                        if ((ride.driver!.vehicleNumber ?? '').isNotEmpty) ride.driver!.vehicleNumber!,
                      ].join(' · ').ifEmpty('Your driver')),
                      trailing: ride.isTrip && (ride.driver!.phone ?? '').isNotEmpty
                          ? IconButton.filled(onPressed: () => _call(ride.driver!.phone!), icon: const Icon(Icons.call))
                          : null,
                    ),
                  ),
                if (ride.status == 'PENDING') ...[
                  const Text('Choose how to pay', style: TextStyle(fontWeight: FontWeight.w600)),
                  const SizedBox(height: 8),
                  Row(children: [
                    Expanded(
                      child: FilledButton.icon(
                        onPressed: _busy ? null : _payUpi,
                        icon: const Icon(Icons.qr_code),
                        label: const Text('Pay with UPI'),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: _busy ? null : () => _action('pay', {'payment_method': 'cash'}, 'Ride confirmed. Pay the driver in cash.'),
                        icon: const Icon(Icons.payments_outlined),
                        label: const Text('Pay cash'),
                      ),
                    ),
                  ]),
                ],
                if (ride.status == 'COMPLETED')
                  ride.rating != null
                      ? ListTile(leading: const Icon(Icons.star, color: Colors.amber), title: Text('You rated this ride ${ride.rating!.toStringAsFixed(0)} ★'))
                      : _RateRide(busy: _busy, onRate: (n) => _action('rate', {'rating': n}, 'Thanks for your rating!')),
                if (ride.canCancel) ...[
                  const SizedBox(height: 16),
                  TextButton.icon(
                    onPressed: _busy
                        ? null
                        : () async {
                            if (await confirmDialog(context, 'Cancel ride?', 'This cannot be undone.', action: 'Cancel ride')) {
                              await _action('cancel', null, 'Ride cancelled.');
                            }
                          },
                    style: TextButton.styleFrom(foregroundColor: Colors.redAccent),
                    icon: const Icon(Icons.close),
                    label: const Text('Cancel ride'),
                  ),
                ],
              ]),
            ),
    );
  }

  Widget _line(IconData icon, Color color, String text) => Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Icon(icon, color: color, size: 20),
        const SizedBox(width: 10),
        Expanded(child: Text(text)),
      ]);
}

class _RateRide extends StatelessWidget {
  const _RateRide({required this.busy, required this.onRate});

  final bool busy;
  final ValueChanged<int> onRate;

  @override
  Widget build(BuildContext context) => Card(
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(children: [
            const Text('How was your ride?'),
            Row(mainAxisAlignment: MainAxisAlignment.center, children: [
              for (var n = 1; n <= 5; n++)
                IconButton(
                  onPressed: busy ? null : () => onRate(n),
                  icon: const Icon(Icons.star_border, color: Colors.amber, size: 32),
                  tooltip: '$n',
                ),
            ]),
          ]),
        ),
      );
}

class _TransactionDialog extends StatefulWidget {
  const _TransactionDialog({required this.upiId, required this.amount, required this.openedApp});

  final String upiId;
  final double amount;
  final bool openedApp;

  @override
  State<_TransactionDialog> createState() => _TransactionDialogState();
}

class _TransactionDialogState extends State<_TransactionDialog> {
  final _txn = TextEditingController();

  @override
  void dispose() {
    _txn.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
        title: const Text('Confirm UPI payment'),
        content: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(widget.openedApp
              ? 'After paying ${money(widget.amount)} in your UPI app, enter the transaction ID.'
              : 'No UPI app opened. Pay ${money(widget.amount)} to ${widget.upiId}, then enter the transaction ID.'),
          const SizedBox(height: 12),
          SelectableText(widget.upiId, style: const TextStyle(fontWeight: FontWeight.w700)),
          const SizedBox(height: 12),
          TextField(controller: _txn, autofocus: true, decoration: const InputDecoration(labelText: 'Transaction ID')),
        ]),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, _txn.text), child: const Text('Confirm')),
        ],
      );
}


extension on String {
  String ifEmpty(String fallback) => isEmpty ? fallback : this;
}

class _LiveChip extends StatelessWidget {
  const _LiveChip({required this.trip});

  final TripTracking trip;

  @override
  Widget build(BuildContext context) {
    final (color, text) = trip.driver == null
        ? (Colors.amber, "Waiting for driver's GPS")
        : trip.driverStale
            ? (Colors.amber, 'Driver GPS signal lost')
            : (Colors.green, 'Live');
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(borderRadius: BorderRadius.circular(99), border: Border.all(color: color)),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Icon(Icons.circle, size: 8, color: color),
        const SizedBox(width: 6),
        Text(text, style: TextStyle(fontSize: 12, color: color, fontWeight: FontWeight.w600)),
      ]),
    );
  }
}

/// "Your ride verification OTP" with an expiry countdown.
class _OtpCard extends StatefulWidget {
  const _OtpCard({required this.otp, required this.onNewCode});

  final Map<String, dynamic> otp;
  final Future<void> Function() onNewCode;

  @override
  State<_OtpCard> createState() => _OtpCardState();
}

class _OtpCardState extends State<_OtpCard> {
  Timer? _tick;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _tick = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) setState(() {});
    });
  }

  Future<void> _newCode() async {
    setState(() => _busy = true);
    await widget.onNewCode();
    if (mounted) setState(() => _busy = false);
  }

  @override
  void dispose() {
    _tick?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final o = widget.otp;
    final expires = DateTime.tryParse(str(o['expires_at']))?.toLocal();
    final left = expires == null ? 0 : expires.difference(DateTime.now()).inSeconds;
    final expired = o['is_expired'] == true || left <= 0;
    final locked = o['is_locked'] == true;
    final scheme = Theme.of(context).colorScheme;
    return Card(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16), side: BorderSide(color: scheme.primary.withAlpha(140))),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(children: [
          const Text('Your ride verification OTP', style: TextStyle(fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          SelectableText(
            expired ? '••••••' : str(o['otp']),
            style: TextStyle(fontSize: 40, fontWeight: FontWeight.w800, letterSpacing: 10,
                color: expired ? Colors.white38 : Colors.white, fontFeatures: const [FontFeature.tabularFigures()]),
          ),
          const SizedBox(height: 6),
          Text(
            locked
                ? 'Too many wrong attempts. Get a new code to try again.'
                : expired
                    ? 'This code has expired.'
                    : 'Share this code with your driver only after you get in. Expires in ${left ~/ 60}:${(left % 60).toString().padLeft(2, '0')}.',
            textAlign: TextAlign.center,
            style: const TextStyle(color: Colors.white60, fontSize: 13),
          ),
          const SizedBox(height: 10),
          if (expired || locked)
            FilledButton.icon(onPressed: _busy ? null : _newCode, icon: const Icon(Icons.refresh), label: const Text('Get a new code'))
          else
            OutlinedButton.icon(onPressed: _busy ? null : _newCode, icon: const Icon(Icons.refresh), label: const Text('Get a new code')),
        ]),
      ),
    );
  }
}
