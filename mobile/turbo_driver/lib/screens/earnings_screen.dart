import 'package:flutter/material.dart';
import 'package:turbo_core/turbo_core.dart';

class EarningsScreen extends StatefulWidget {
  const EarningsScreen({super.key});

  @override
  State<EarningsScreen> createState() => _EarningsScreenState();
}

class _EarningsScreenState extends State<EarningsScreen> {
  Map<String, dynamic>? _data;
  String? _error;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load() async {
    try {
      final json = await AuthScope.read(context).api.get('/driver/earnings/');
      if (mounted) {
        setState(() {
          _data = json as Map<String, dynamic>;
          _error = null;
        });
      }
    } catch (e) {
      if (mounted) setState(() => _error = errorText(e));
    }
  }

  @override
  Widget build(BuildContext context) {
    final d = _data;
    return Scaffold(
      appBar: AppBar(title: const Text('Earnings')),
      body: d == null
          ? Center(child: _error != null ? ErrorBanner(_error, onRetry: _load) : const CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _load,
              child: ListView(padding: const EdgeInsets.all(12), children: [
                StatGrid([
                  StatCard('Today', money(toDouble(d['daily_earnings']))),
                  StatCard('Last 7 days', money(toDouble(d['weekly_earnings']))),
                  StatCard('Last 30 days', money(toDouble(d['monthly_earnings']))),
                  StatCard('All time', money(toDouble(d['total_earnings']))),
                  StatCard('Completed rides', '${d['completed_rides']}'),
                  StatCard('Rating', d['average_rating'] == null ? '—' : '${toDouble(d['average_rating']).toStringAsFixed(1)} ★'),
                ]),
                const SizedBox(height: 12),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(14),
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text('Daily earnings · last 30 days', style: Theme.of(context).textTheme.titleMedium),
                      const SizedBox(height: 12),
                      BarChart(
                        labels: [for (final r in d['chart'] as List) shortDay(DateTime.parse(r['date'].toString()))],
                        values: [for (final r in d['chart'] as List) toDouble(r['total'])],
                      ),
                    ]),
                  ),
                ),
                const SizedBox(height: 12),
                Text('Recent earnings', style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 6),
                if ((d['recent'] as List).isEmpty) const EmptyState('Complete a ride to see earnings here.'),
                for (final e in d['recent'] as List)
                  Card(
                    child: ListTile(
                      title: Text(e['pickup_location'] == null ? 'Earning' : '${e['pickup_location']} → ${e['drop_location']}',
                          maxLines: 1, overflow: TextOverflow.ellipsis),
                      subtitle: Text('${formatDay(DateTime.tryParse(e['date'].toString()))}${e['rider_name'] != null ? ' · ${e['rider_name']}' : ''}'),
                      trailing: Text(money(toDouble(e['amount'])), style: const TextStyle(fontWeight: FontWeight.w700)),
                    ),
                  ),
              ]),
            ),
    );
  }
}

class HistoryScreen extends StatelessWidget {
  const HistoryScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final api = AuthScope.read(context).api;
    return Scaffold(
      appBar: AppBar(title: const Text('Ride history')),
      body: PagedListView<Ride>(
        emptyText: 'No finished rides yet.',
        load: (page) async => PageOf.fromJson(await api.get('/driver/rides/history/', query: {'page': '$page'}), Ride.fromJson),
        itemBuilder: (context, r) => Card(
          child: ListTile(
            title: Text('${r.pickup} → ${r.drop}', maxLines: 2, overflow: TextOverflow.ellipsis),
            subtitle: Text('${formatWhen(r.createdAt)} · ${r.rider.fullName}${r.rating != null ? ' · ${r.rating!.toStringAsFixed(0)}★' : ''}'),
            trailing: Column(mainAxisAlignment: MainAxisAlignment.center, crossAxisAlignment: CrossAxisAlignment.end, children: [
              Text(money(r.fare), style: const TextStyle(fontWeight: FontWeight.w700)),
              const SizedBox(height: 4),
              StatusChip(r.status, r.statusDisplay),
            ]),
          ),
        ),
      ),
    );
  }
}
