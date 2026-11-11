import 'dart:async';

import 'package:flutter/material.dart';
import 'package:turbo_core/turbo_core.dart';

/// All rides (or only paid ones when [payments] is true) with status filter + search.
class RidesScreen extends StatefulWidget {
  const RidesScreen({super.key, this.payments = false});

  final bool payments;

  @override
  State<RidesScreen> createState() => _RidesScreenState();
}

class _RidesScreenState extends State<RidesScreen> {
  String _status = '';
  String _search = '';
  Timer? _debounce;
  List<Choice> _statuses = const [];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      try {
        final meta = await AuthScope.read(context).meta();
        if (mounted) setState(() => _statuses = meta.rideStatuses);
      } catch (_) {}
    });
  }

  @override
  void dispose() {
    _debounce?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final api = AuthScope.read(context).api;
    final path = widget.payments ? '/admin/rides/payments/' : '/admin/rides/';
    return Scaffold(
      appBar: AppBar(title: Text(widget.payments ? 'Payments' : 'Rides')),
      body: Column(children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 0, 12, 4),
          child: TextField(
            decoration: const InputDecoration(hintText: 'Search place or name', prefixIcon: Icon(Icons.search), isDense: true),
            onChanged: (v) {
              _debounce?.cancel();
              _debounce = Timer(const Duration(milliseconds: 400), () => setState(() => _search = v.trim()));
            },
          ),
        ),
        SizedBox(
          height: 48,
          child: ListView(scrollDirection: Axis.horizontal, padding: const EdgeInsets.symmetric(horizontal: 12), children: [
            for (final c in [Choice('', 'All'), ..._statuses])
              Padding(
                padding: const EdgeInsets.only(right: 6),
                child: ChoiceChip(label: Text(c.label), selected: _status == c.value, onSelected: (_) => setState(() => _status = c.value)),
              ),
          ]),
        ),
        Expanded(
          child: PagedListView<Ride>(
            key: ValueKey('$_status|$_search'),
            emptyText: 'No rides match.',
            load: (page) async => PageOf.fromJson(
              await api.get(path, query: {'page': '$page', 'status': _status, 'search': _search}),
              Ride.fromJson,
            ),
            itemBuilder: (context, r) => AdminRideTile(r, showPayment: widget.payments),
          ),
        ),
      ]),
    );
  }
}

class AdminRideTile extends StatelessWidget {
  const AdminRideTile(this.ride, {super.key, this.showPayment = false});

  final Ride ride;
  final bool showPayment;

  @override
  Widget build(BuildContext context) {
    final r = ride;
    return Card(
      child: ExpansionTile(
        shape: const Border(),
        title: Text('${r.pickup} → ${r.drop}', maxLines: 1, overflow: TextOverflow.ellipsis),
        subtitle: Text('#${r.id} · ${formatWhen(r.createdAt)} · ${r.rider.fullName}'),
        trailing: Column(mainAxisAlignment: MainAxisAlignment.center, crossAxisAlignment: CrossAxisAlignment.end, children: [
          Text(money(r.fare), style: const TextStyle(fontWeight: FontWeight.w700)),
          const SizedBox(height: 4),
          StatusChip(r.status, r.statusDisplay),
        ]),
        childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
        expandedCrossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _row('From', r.pickup),
          _row('To', r.drop),
          _row('Vehicle', '${r.carTypeDisplay} · ${r.distance.toStringAsFixed(2)} km'),
          _row('Rider', '${r.rider.fullName}${(r.rider.phone ?? '').isNotEmpty ? ' · ${r.rider.phone}' : ''}'),
          _row('Driver', r.driver == null ? '—' : '${r.driver!.fullName} · ${r.driver!.phone ?? ''}'),
          _row('Payment', r.paymentMethodDisplay == null ? 'Unpaid' : '${r.paymentMethodDisplay}${r.transactionId != null ? ' · ${r.transactionId}' : ''}'),
          if (r.rating != null) _row('Rating', '${r.rating!.toStringAsFixed(0)} ★'),
        ],
      ),
    );
  }

  Widget _row(String k, String v) => Padding(
        padding: const EdgeInsets.only(top: 4),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          SizedBox(width: 70, child: Text(k, style: const TextStyle(color: Colors.white54))),
          Expanded(child: Text(v)),
        ]),
      );
}
