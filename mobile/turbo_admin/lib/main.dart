import 'package:flutter/material.dart';
import 'package:turbo_core/turbo_core.dart';

import 'screens/more_screen.dart';
import 'screens/overview_screen.dart';
import 'screens/people_screens.dart';
import 'screens/rides_screen.dart';

void main() {
  runApp(TurboApp(
    role: 'admin',
    title: 'Turbo Admin',
    seed: const Color(0xFFF59E0B),
    allowRegister: false, // admins are created by other admins
    home: (_) => const AdminHome(),
  ));
}

class AdminHome extends StatefulWidget {
  const AdminHome({super.key});

  @override
  State<AdminHome> createState() => _AdminHomeState();
}

class _AdminHomeState extends State<AdminHome> {
  int _tab = 0;
  int _visit = 0;

  @override
  Widget build(BuildContext context) {
    // Tabs reload when opened so numbers are fresh.
    final pages = [
      OverviewScreen(key: ValueKey('o$_visit')),
      RidesScreen(key: ValueKey('r$_visit')),
      RidersScreen(key: ValueKey('ri$_visit')),
      DriversScreen(key: ValueKey('d$_visit')),
      const MoreScreen(),
    ];
    return Scaffold(
      body: IndexedStack(index: _tab, children: pages),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _tab,
        onDestinationSelected: (i) => setState(() {
          if (i != _tab && i != 4) _visit++;
          _tab = i;
        }),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.dashboard_outlined), selectedIcon: Icon(Icons.dashboard), label: 'Overview'),
          NavigationDestination(icon: Icon(Icons.local_taxi_outlined), selectedIcon: Icon(Icons.local_taxi), label: 'Rides'),
          NavigationDestination(icon: Icon(Icons.people_outline), selectedIcon: Icon(Icons.people), label: 'Riders'),
          NavigationDestination(icon: Icon(Icons.badge_outlined), selectedIcon: Icon(Icons.badge), label: 'Drivers'),
          NavigationDestination(icon: Icon(Icons.more_horiz), label: 'More'),
        ],
      ),
    );
  }
}
