import 'package:flutter/material.dart';
import 'package:turbo_core/turbo_core.dart';

import 'screens/dashboard_screen.dart';
import 'screens/earnings_screen.dart';
import 'screens/profile_screen.dart';

void main() {
  runApp(TurboApp(
    role: 'driver',
    title: 'Turbo Driver',
    seed: const Color(0xFF22C55E),
    home: (_) => const DriverHome(),
  ));
}

class DriverHome extends StatefulWidget {
  const DriverHome({super.key});

  @override
  State<DriverHome> createState() => _DriverHomeState();
}

class _DriverHomeState extends State<DriverHome> {
  int _tab = 0;
  int _visit = 0; // bump to reload the tab being opened

  @override
  Widget build(BuildContext context) {
    final pages = [
      const DashboardScreen(),
      EarningsScreen(key: ValueKey('earn$_visit')),
      HistoryScreen(key: ValueKey('hist$_visit')),
      const ProfileScreen(),
    ];
    return Scaffold(
      body: IndexedStack(index: _tab, children: pages),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _tab,
        onDestinationSelected: (i) => setState(() {
          if (i != _tab && (i == 1 || i == 2)) _visit++;
          _tab = i;
        }),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.local_taxi_outlined), selectedIcon: Icon(Icons.local_taxi), label: 'Rides'),
          NavigationDestination(icon: Icon(Icons.account_balance_wallet_outlined), selectedIcon: Icon(Icons.account_balance_wallet), label: 'Earnings'),
          NavigationDestination(icon: Icon(Icons.history), label: 'History'),
          NavigationDestination(icon: Icon(Icons.person_outline), selectedIcon: Icon(Icons.person), label: 'Profile'),
        ],
      ),
    );
  }
}
