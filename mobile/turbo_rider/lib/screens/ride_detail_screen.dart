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

  @override
  void initState() {
    super.initState();
    _ride = widget.initial;
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
    // Keep the status fresh while the ride is in progress.
    _poll = Timer.periodic(const Duration(seconds: 10), (_) {
      if (_ride?.isActive ?? true) _load(quiet: true);
    });
  }

  @override
  void dispose() {
    _poll?.cancel();
    super.dispose();
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
                if (ride.driver != null)
                  Card(
                    child: ListTile(
                      leading: CircleAvatar(
                        backgroundImage: ride.driver!.photo != null ? NetworkImage(ride.driver!.photo!) : null,
                        child: ride.driver!.photo == null ? const Icon(Icons.person) : null,
                      ),
                      title: Text(ride.driver!.fullName),
                      subtitle: Text(ride.driver!.vehicleInfo?.isNotEmpty == true ? ride.driver!.vehicleInfo! : 'Your driver'),
                      trailing: ride.status == 'ACCEPTED' && (ride.driver!.phone ?? '').isNotEmpty
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
                if (ride.status == 'CONFIRMED')
                  const ListTile(
                    leading: SizedBox(width: 24, height: 24, child: CircularProgressIndicator(strokeWidth: 2)),
                    title: Text('Waiting for a driver to accept…'),
                  ),
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
