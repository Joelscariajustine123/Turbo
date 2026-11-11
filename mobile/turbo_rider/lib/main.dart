import 'package:flutter/material.dart';
import 'package:turbo_core/turbo_core.dart';

import 'screens/book_screen.dart';
import 'screens/ride_detail_screen.dart';

void main() {
  runApp(TurboApp(
    role: 'rider',
    title: 'Turbo Rider',
    seed: const Color(0xFF3B82F6),
    home: (_) => const RiderHome(),
  ));
}

class RiderHome extends StatefulWidget {
  const RiderHome({super.key});

  @override
  State<RiderHome> createState() => _RiderHomeState();
}

class _RiderHomeState extends State<RiderHome> {
  int _tab = 0;
  int _ridesVersion = 0; // bump to rebuild (reload) the rides list

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(index: _tab, children: [
        BookScreen(onBooked: () => setState(() => _ridesVersion++)),
        RidesScreen(key: ValueKey(_ridesVersion)),
        Scaffold(appBar: AppBar(title: const Text('Account')), body: const AccountScreen()),
      ]),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _tab,
        onDestinationSelected: (i) => setState(() {
          if (i == 1 && _tab != 1) _ridesVersion++;
          _tab = i;
        }),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.local_taxi_outlined), selectedIcon: Icon(Icons.local_taxi), label: 'Book'),
          NavigationDestination(icon: Icon(Icons.receipt_long_outlined), selectedIcon: Icon(Icons.receipt_long), label: 'My rides'),
          NavigationDestination(icon: Icon(Icons.person_outline), selectedIcon: Icon(Icons.person), label: 'Account'),
        ],
      ),
    );
  }
}

class RidesScreen extends StatefulWidget {
  const RidesScreen({super.key});

  @override
  State<RidesScreen> createState() => _RidesScreenState();
}

class _RidesScreenState extends State<RidesScreen> {
  String _state = '';
  int _version = 0;

  @override
  Widget build(BuildContext context) {
    final api = AuthScope.read(context).api;
    return Scaffold(
      appBar: AppBar(title: const Text('My rides')),
      body: PagedListView<Ride>(
        key: ValueKey('$_state-$_version'),
        pollEvery: const Duration(seconds: 20),
        emptyText: 'No rides yet. Book one from the Book tab.',
        header: SegmentedButton<String>(
          segments: const [
            ButtonSegment(value: '', label: Text('All')),
            ButtonSegment(value: 'active', label: Text('Active')),
            ButtonSegment(value: 'past', label: Text('Past')),
          ],
          selected: {_state},
          onSelectionChanged: (s) => setState(() => _state = s.first),
        ),
        load: (page) async => PageOf.fromJson(
          await api.get('/rider/rides/', query: {'page': '$page', 'state': _state}),
          Ride.fromJson,
        ),
        itemBuilder: (context, ride) => Card(
          child: ListTile(
            onTap: () => Navigator.of(context)
                .push(MaterialPageRoute(builder: (_) => RideDetailScreen(rideId: ride.id, initial: ride)))
                .then((_) { if (mounted) setState(() => _version++); }),
            title: Text(ride.drop, maxLines: 1, overflow: TextOverflow.ellipsis),
            subtitle: Text('${formatWhen(ride.createdAt)} · ${ride.carTypeDisplay}'),
            trailing: Column(mainAxisAlignment: MainAxisAlignment.center, crossAxisAlignment: CrossAxisAlignment.end, children: [
              Text(money(ride.fare), style: const TextStyle(fontWeight: FontWeight.w700)),
              const SizedBox(height: 4),
              StatusChip(ride.status, ride.statusDisplay),
            ]),
          ),
        ),
      ),
    );
  }
}
