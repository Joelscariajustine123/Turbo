import 'package:flutter/material.dart';
import 'package:turbo_core/turbo_core.dart';

import 'rides_screen.dart';

class OverviewScreen extends StatefulWidget {
  const OverviewScreen({super.key});

  @override
  State<OverviewScreen> createState() => _OverviewScreenState();
}

class _OverviewScreenState extends State<OverviewScreen> {
  Map<String, dynamic>? _stats;
  String? _error;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load() async {
    try {
      final json = await AuthScope.read(context).api.get('/admin/stats/');
      if (mounted) {
        setState(() {
          _stats = json as Map<String, dynamic>;
          _error = null;
        });
      }
    } catch (e) {
      if (mounted) setState(() => _error = errorText(e));
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = _stats;
    return Scaffold(
      appBar: AppBar(title: const Text('Overview')),
      body: s == null
          ? Center(child: _error != null ? ErrorBanner(_error, onRetry: _load) : const CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _load,
              child: ListView(padding: const EdgeInsets.all(12), children: [
                ErrorBanner(_error),
                StatGrid([
                  StatCard('Revenue this month', money(toDouble(s['monthly_revenue'])), hint: '${money(toDouble(s['total_revenue']))} all time'),
                  StatCard('Completed rides', '${s['total_bookings']}', hint: '${s['total_rides']} booked in total'),
                  StatCard('Awaiting payment', '${s['pending_requests']}'),
                  StatCard('Waiting for driver', '${s['waiting_for_driver']}'),
                  StatCard('On the road', '${s['ongoing_rides']}'),
                  StatCard('Riders / Drivers', '${s['total_riders']} / ${s['total_drivers']}'),
                ]),
                const SizedBox(height: 16),
                Text('Latest rides', style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 8),
                if ((s['recent_rides'] as List).isEmpty) const EmptyState('No rides yet.'),
                for (final r in s['recent_rides'] as List)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: AdminRideTile(Ride.fromJson(r as Map<String, dynamic>)),
                  ),
              ]),
            ),
    );
  }
}
