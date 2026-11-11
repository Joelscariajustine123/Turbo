import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import 'models.dart';

LatLng? _point(dynamic j) =>
    j == null ? null : LatLng(toDouble((j as Map)['lat']), toDouble(j['lng']));

List<LatLng> _line(dynamic geometry) => geometry is List
    ? geometry.map((p) => LatLng(toDouble((p as List)[0]), toDouble(p[1]))).toList()
    : const [];

/// Live trip state from /api/rider/ride/tracking/ or /api/driver/location/update/.
class TripTracking {
  TripTracking({
    required this.rideId,
    required this.status,
    required this.stage,
    required this.stageLabel,
    required this.otpVerified,
    required this.trackingActive,
    required this.nearTarget,
    this.pickup,
    this.pickupLabel = '',
    this.drop,
    this.dropLabel = '',
    this.driver,
    this.driverHeading,
    this.driverStale = false,
    this.driverAgeSeconds,
    this.route = const [],
    this.tripRoute = const [],
    this.distanceToPickupKm,
    this.distanceToDestinationKm,
    this.etaMinutes,
    this.driverCard,
  });

  factory TripTracking.fromJson(Map<String, dynamic> j) {
    final loc = j['driver_location'] as Map<String, dynamic>?;
    return TripTracking(
      rideId: j['ride_id'] as int,
      status: str(j['status']),
      stage: j['stage'] as String?,
      stageLabel: str(j['stage_label']),
      otpVerified: j['otp_verified'] == true,
      trackingActive: j['tracking_active'] == true,
      nearTarget: j['near_target'] == true,
      pickup: _point(j['pickup']),
      pickupLabel: str((j['pickup'] as Map?)?['label']),
      drop: _point(j['drop']),
      dropLabel: str((j['drop'] as Map?)?['label']),
      driver: loc == null ? null : LatLng(toDouble(loc['lat']), toDouble(loc['lng'])),
      driverHeading: toDoubleOrNull(loc?['heading']),
      driverStale: loc?['is_stale'] == true,
      driverAgeSeconds: toDoubleOrNull(loc?['age_seconds']),
      route: _line((j['route'] as Map?)?['geometry']),
      tripRoute: _line((j['trip_route'] as Map?)?['geometry']),
      distanceToPickupKm: toDoubleOrNull(j['distance_to_pickup_km']),
      distanceToDestinationKm: toDoubleOrNull(j['distance_to_destination_km']),
      etaMinutes: j['eta_minutes'] as int?,
      driverCard: j['driver'] as Map<String, dynamic>?,
    );
  }

  final int rideId;
  final String status;
  final String? stage; // 'pickup' | 'destination' | null
  final String stageLabel;
  final bool otpVerified;
  final bool trackingActive;
  final bool nearTarget;
  final LatLng? pickup;
  final String pickupLabel;
  final LatLng? drop;
  final String dropLabel;
  final LatLng? driver;
  final double? driverHeading;
  final bool driverStale;
  final double? driverAgeSeconds;
  final List<LatLng> route;
  final List<LatLng> tripRoute;
  final double? distanceToPickupKm;
  final double? distanceToDestinationKm;
  final int? etaMinutes;
  final Map<String, dynamic>? driverCard;

  bool get isTrip => const ['ACCEPTED', 'ARRIVED', 'IN_PROGRESS'].contains(status);
  bool get needsOtp => (status == 'ACCEPTED' || status == 'ARRIVED') && !otpVerified;
  LatLng? get target => stage == 'destination' ? drop : pickup;
}

String formatKm(double? km) =>
    km == null ? '—' : km < 1 ? '${(km * 1000).round()} m' : '${km.toStringAsFixed(1)} km';

/// Distance + ETA tiles.
class TripMetrics extends StatelessWidget {
  const TripMetrics(this.t, {super.key});

  final TripTracking t;

  @override
  Widget build(BuildContext context) {
    Widget tile(String label, String value) => Expanded(
          child: Card(
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 12),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(label.toUpperCase(), style: const TextStyle(fontSize: 10, color: Colors.white54, letterSpacing: .6)),
                const SizedBox(height: 2),
                Text(value, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
              ]),
            ),
          ),
        );
    return Row(children: [
      tile('To pickup', t.status == 'IN_PROGRESS' ? 'Picked up' : t.status == 'ARRIVED' ? 'Here' : formatKm(t.distanceToPickupKm)),
      const SizedBox(width: 6),
      tile('To drop', formatKm(t.distanceToDestinationKm)),
      const SizedBox(width: 6),
      tile('ETA', t.etaMinutes == null ? '—' : t.status == 'ARRIVED' ? 'Now' : '${t.etaMinutes} min'),
    ]);
  }
}

/// Map with pickup/drop pins, the moving car and the active route.
/// The camera is fitted when the stage changes; afterwards the user can pan freely.
class TripMap extends StatefulWidget {
  const TripMap({super.key, required this.tracking, this.me, this.meHeading, this.height = 320, this.userAgent = 'com.turbocab'});

  final TripTracking? tracking;
  final LatLng? me; // the driver's own GPS (driver app)
  final double? meHeading;
  final double height;
  final String userAgent;

  @override
  State<TripMap> createState() => _TripMapState();
}

class _TripMapState extends State<TripMap> {
  final _map = MapController();
  bool _ready = false;
  String? _fittedFor;

  LatLng? get _car => widget.tracking?.driver ?? widget.me;

  void _fit() {
    if (!_ready) return;
    final t = widget.tracking;
    final key = '${t?.rideId}:${t?.stage}:${_car != null}';
    if (key == _fittedFor) return;
    _fittedFor = key;
    final pts = [_car, t?.target].whereType<LatLng>().toList();
    if (pts.length == 1) _map.move(pts.first, 15);
    if (pts.length > 1) {
      _map.fitCamera(CameraFit.bounds(bounds: LatLngBounds.fromPoints(pts), padding: const EdgeInsets.all(48), maxZoom: 16));
    }
  }

  @override
  void didUpdateWidget(covariant TripMap oldWidget) {
    super.didUpdateWidget(oldWidget);
    WidgetsBinding.instance.addPostFrameCallback((_) => _fit());
  }

  @override
  Widget build(BuildContext context) {
    final t = widget.tracking;
    final car = _car;
    final heading = t?.driver != null ? t?.driverHeading : widget.meHeading;
    final scheme = Theme.of(context).colorScheme;
    return SizedBox(
      height: widget.height,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(14),
        child: FlutterMap(
          mapController: _map,
          options: MapOptions(
            initialCenter: car ?? t?.pickup ?? const LatLng(11.8745, 75.3704),
            initialZoom: 14,
            onMapReady: () {
              _ready = true;
              _fit();
            },
          ),
          children: [
            TileLayer(urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png', userAgentPackageName: widget.userAgent),
            if (t != null && t.stage == 'pickup' && t.tripRoute.length >= 2)
              PolylineLayer(polylines: [
                Polyline(points: t.tripRoute, strokeWidth: 4, color: Colors.blueGrey.shade300, pattern: StrokePattern.dashed(segments: const [10, 8])),
              ]),
            if (t != null && t.route.length >= 2)
              PolylineLayer(polylines: [Polyline(points: t.route, strokeWidth: 6, color: scheme.primary)]),
            MarkerLayer(markers: [
              if (t?.pickup != null) _pin(t!.pickup!, 'P', Colors.green.shade700),
              if (t?.drop != null) _pin(t!.drop!, 'D', Colors.red.shade700),
              if (car != null)
                Marker(
                  point: car,
                  width: 44,
                  height: 44,
                  child: Transform.rotate(
                    angle: (heading ?? 0) * 3.1415926535 / 180,
                    child: Container(
                      decoration: BoxDecoration(color: scheme.primary.withAlpha(46), shape: BoxShape.circle),
                      child: Icon(Icons.navigation, color: scheme.primary, size: 30),
                    ),
                  ),
                ),
            ]),
            const RichAttributionWidget(attributions: [TextSourceAttribution('OpenStreetMap contributors')]),
          ],
        ),
      ),
    );
  }

  Marker _pin(LatLng p, String label, Color color) => Marker(
        point: p,
        width: 36,
        height: 36,
        alignment: Alignment.topCenter,
        child: Container(
          decoration: BoxDecoration(color: color, shape: BoxShape.circle, border: Border.all(color: Colors.white, width: 3)),
          alignment: Alignment.center,
          child: Text(label, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w800, fontSize: 13)),
        ),
      );
}
