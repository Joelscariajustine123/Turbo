import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:turbo_core/turbo_core.dart';
import 'package:turbo_driver/main.dart';

// Smoke tests: there is no server here, so API calls fail and every screen
// must show its error/empty state instead of crashing.
void main() {
  Widget app() => TurboApp(role: 'driver', title: 'Turbo Driver', seed: const Color(0xFF22C55E), home: (_) => const DriverHome());

  testWidgets('logged out: shows the login screen', (tester) async {
    SharedPreferences.setMockInitialValues({});
    await tester.pumpWidget(app());
    await tester.pump(const Duration(milliseconds: 500));
    expect(find.text('Sign in'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('saved session: opens home and every tab renders', (tester) async {
    SharedPreferences.setMockInitialValues({
      'turbo.access': 'a',
      'turbo.refresh': 'r',
      'turbo.user': jsonEncode({
        'id': 1, 'username': 'u', 'email': 'u@example.com', 'full_name': 'Test User',
        'phone': '9000000000', 'role': 'driver', 'is_active': true, 'date_joined': null,
      }),
    });
    await tester.pumpWidget(app());
    for (var i = 0; i < 10; i++) {
      await tester.pump(const Duration(milliseconds: 300));
    }
    expect(find.text('Sign in'), findsNothing);
    for (final tab in ['Earnings', 'History', 'Profile']) {
      await tester.tap(find.descendant(of: find.byType(NavigationBar), matching: find.text(tab)));
      for (var i = 0; i < 5; i++) {
        await tester.pump(const Duration(milliseconds: 300));
      }
    }
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox()); // dispose timers
  });
}
