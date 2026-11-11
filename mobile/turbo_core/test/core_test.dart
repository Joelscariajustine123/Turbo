import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:turbo_core/turbo_core.dart';

// A ride exactly as GET /api/rider/rides/{id}/ returns it.
const rideJson = {
  'id': 16,
  'pickup_location': 'Kannur',
  'drop_location': 'Thalassery',
  'pickup_lat': 11.8745,
  'pickup_lng': 75.3704,
  'drop_lat': 11.7481,
  'drop_lng': 75.489,
  'car_type': 'auto',
  'car_type_display': 'Auto',
  'distance': 24.81,
  'fare': 347.72,
  'status': 'ACCEPTED',
  'status_display': 'Accepted',
  'payment_method': 'UPI',
  'payment_method_display': 'UPI',
  'transaction_id': 'T123',
  'created_at': '2026-11-11T04:56:10.123456Z',
  'updated_at': '2026-11-11T04:57:00Z',
  'rider': {'id': 3, 'full_name': 'Smoke Rider', 'phone': '9000000001'},
  'driver': {'id': 4, 'full_name': 'Smoke Driver', 'phone': '9000000002', 'vehicle_info': 'Swift', 'profile_photo': null},
  'rating': null,
  'can_cancel': false,
};

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('models', () {
    test('Ride parses an API response', () {
      final r = Ride.fromJson(Map<String, dynamic>.from(rideJson));
      expect(r.fare, 347.72);
      expect(r.driver!.vehicleInfo, 'Swift');
      expect(r.rider.phone, '9000000001');
      expect(r.isActive, isTrue);
      expect(r.rating, isNull);
    });

    test('PageOf parses DRF pagination', () {
      final page = PageOf.fromJson({'count': 1, 'next': null, 'previous': null, 'results': [rideJson]}, Ride.fromJson);
      expect(page.count, 1);
      expect(page.hasNext, isFalse);
      expect(page.results.single.id, 16);
    });

    test('numbers sent as strings still parse', () => expect(toDouble('12.50'), 12.5));
  });

  group('formatting', () {
    test('money uses Indian grouping', () {
      expect(money(347.72), '₹347.72');
      expect(money(1234567.5), '₹12,34,567.50');
      expect(money(null), '₹0.00');
    });

    test('errorText drops the Exception prefix', () {
      expect(errorText(Exception('Location denied')), 'Location denied');
      expect(errorText(ApiException('Bad request', 400)), 'Bad request');
    });
  });

  group('ApiClient', () {
    setUp(() => SharedPreferences.setMockInitialValues({}));

    test('error responses become ApiException with the server detail', () async {
      final api = ApiClient(
        baseUrl: 'http://test',
        client: MockClient((_) async => http.Response(jsonEncode({'detail': 'Invalid email or password.'}), 401)),
      );
      expect(
        () => api.postPublic('/auth/login/', {'email': 'a@b.c', 'password': 'x'}),
        throwsA(isA<ApiException>().having((e) => e.message, 'message', 'Invalid email or password.')),
      );
    });

    test('refreshes the access token once on 401 and retries', () async {
      var calls = 0;
      final api = ApiClient(
        baseUrl: 'http://test',
        client: MockClient((req) async {
          calls++;
          if (req.url.path == '/api/auth/refresh/') {
            return http.Response(jsonEncode({'access': 'new-access', 'refresh': 'new-refresh'}), 200);
          }
          if (req.headers['Authorization'] == 'Bearer new-access') {
            return http.Response(jsonEncode({'id': 1}), 200);
          }
          return http.Response(jsonEncode({'detail': 'expired'}), 401);
        }),
      );
      await api.saveSession({'access': 'old', 'refresh': 'r1'});
      final me = await api.get('/auth/me/');
      expect(me['id'], 1);
      expect(calls, 3); // 401, refresh, retry
      expect(api.refreshToken, 'new-refresh');
    });

    test('expired refresh token clears the session and notifies', () async {
      var expired = false;
      final api = ApiClient(
        baseUrl: 'http://test',
        client: MockClient((_) async => http.Response(jsonEncode({'detail': 'nope'}), 401)),
      )..onSessionExpired = () => expired = true;
      await api.saveSession({'access': 'old', 'refresh': 'r1'});
      await expectLater(api.get('/auth/me/'), throwsA(isA<ApiException>()));
      expect(expired, isTrue);
      expect(api.hasSession, isFalse);
    });

    test('query parameters skip empty values', () {
      final api = ApiClient(baseUrl: 'http://test/');
      expect(api.uri('/admin/rides/', {'page': '2', 'status': ''}).toString(), 'http://test/api/admin/rides/?page=2');
    });
  });
}
