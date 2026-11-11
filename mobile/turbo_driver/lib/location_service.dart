import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:geolocator/geolocator.dart';
import 'package:latlong2/latlong.dart';
import 'package:turbo_core/turbo_core.dart';

enum GpsState { off, waiting, live, weak, denied, serviceOff }

/// Shares the driver's GPS with the server every 3 s while online.
///
/// On Android this runs as a foreground service (persistent notification), so
/// tracking continues with the screen locked — something a browser can't do.
/// On iOS it uses background location updates (UIBackgroundModes: location).
class DriverLocationService extends ChangeNotifier {
  DriverLocationService(this.api);

  final ApiClient api;

  GpsState gps = GpsState.off;
  bool networkOk = true;
  DateTime? lastSentAt;
  Position? position;
  TripTracking? tracking;
  String? error;

  StreamSubscription<Position>? _sub;
  Timer? _timer;
  bool _running = false;
  void Function(String message)? onStoppedByServer;
  void Function()? onTripChanged;

  bool get running => _running;
  LatLng? get latLng => position == null ? null : LatLng(position!.latitude, position!.longitude);

  Future<void> start() async {
    if (_running) return;
    error = null;
    LocationPermission permission;
    try {
      if (!await Geolocator.isLocationServiceEnabled()) {
        gps = GpsState.serviceOff;
        error = 'Location is turned off. Turn it on to share your position.';
        notifyListeners();
        return;
      }
      permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) permission = await Geolocator.requestPermission();
    } catch (_) {
      gps = GpsState.serviceOff;
      error = 'Location is not available on this device.';
      notifyListeners();
      return;
    }
    if (permission == LocationPermission.denied || permission == LocationPermission.deniedForever) {
      gps = GpsState.denied;
      error = 'Location permission is needed to go online. Allow it in Settings.';
      notifyListeners();
      return;
    }
    _running = true;
    gps = GpsState.waiting;
    notifyListeners();
    _sub = Geolocator.getPositionStream(locationSettings: _settings()).listen(
      (p) {
        // A rough network fix right after a good GPS one would make the car jump: skip it.
        final prev = position;
        if (p.accuracy > 150 && prev != null && prev.accuracy <= 150 &&
            DateTime.now().difference(prev.timestamp) < const Duration(seconds: 20)) {
          return;
        }
        position = p;
        gps = GpsState.live;
        notifyListeners();
      },
      onError: (Object e) {
        gps = GpsState.weak;
        notifyListeners();
      },
    );
    _tick();
  }

  LocationSettings _settings() {
    if (defaultTargetPlatform == TargetPlatform.android) {
      return AndroidSettings(
        accuracy: LocationAccuracy.bestForNavigation,
        distanceFilter: 0,
        intervalDuration: const Duration(seconds: 2),
        foregroundNotificationConfig: const ForegroundNotificationConfig(
          notificationTitle: 'Turbo Driver is sharing your location',
          notificationText: 'Riders see your position during rides you accept.',
          enableWakeLock: true,
        ),
      );
    }
    if (defaultTargetPlatform == TargetPlatform.iOS) {
      return AppleSettings(
        accuracy: LocationAccuracy.bestForNavigation,
        activityType: ActivityType.automotiveNavigation,
        distanceFilter: 0,
        pauseLocationUpdatesAutomatically: false,
        allowBackgroundLocationUpdates: true,
        showBackgroundLocationIndicator: true,
      );
    }
    return const LocationSettings(accuracy: LocationAccuracy.high);
  }

  /// One update, then schedule the next one 3 s after this one *started* (never overlapping).
  Future<void> _tick() async {
    if (!_running) return;
    final started = DateTime.now();
    final p = position;
    if (p != null) {
      if (DateTime.now().difference(p.timestamp) > const Duration(seconds: 15)) gps = GpsState.weak;
      try {
        final json = await api.post('/driver/location/update/', {
          'latitude': double.parse(p.latitude.toStringAsFixed(6)),
          'longitude': double.parse(p.longitude.toStringAsFixed(6)),
          'accuracy': p.accuracy.isFinite ? p.accuracy.roundToDouble() : null,
          'speed': p.speed >= 0 ? double.parse((p.speed * 3.6).toStringAsFixed(1)) : null,
          'heading': p.heading >= 0 && p.heading <= 360 ? p.heading.roundToDouble() : null,
        }) as Map<String, dynamic>;
        networkOk = true;
        lastSentAt = DateTime.now();
        final t = json['tracking'] == null ? null : TripTracking.fromJson(json['tracking'] as Map<String, dynamic>);
        final changed = t?.status != tracking?.status || t?.rideId != tracking?.rideId;
        tracking = t;
        if (changed) onTripChanged?.call();
      } on ApiException catch (e) {
        if (e.status == 409) {
          // The server says we're offline: stop sharing.
          await stop();
          onStoppedByServer?.call(e.message);
          return;
        }
        networkOk = false;
      } catch (_) {
        networkOk = false;
      }
      notifyListeners();
    }
    if (!_running) return;
    final wait = const Duration(seconds: 3) - DateTime.now().difference(started);
    _timer = Timer(wait.isNegative ? Duration.zero : wait, _tick);
  }

  Future<void> stop() async {
    _running = false;
    _timer?.cancel();
    await _sub?.cancel();
    _sub = null;
    gps = GpsState.off;
    tracking = null;
    notifyListeners();
  }

  @override
  void dispose() {
    _running = false;
    _timer?.cancel();
    _sub?.cancel();
    super.dispose();
  }
}
