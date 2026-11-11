import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:turbo_core/turbo_core.dart';

import '../geo.dart';
import 'ride_detail_screen.dart';

const _kannur = LatLng(11.8745, 75.3704);

class BookScreen extends StatefulWidget {
  const BookScreen({super.key, this.onBooked});

  final VoidCallback? onBooked;

  @override
  State<BookScreen> createState() => _BookScreenState();
}

class _BookScreenState extends State<BookScreen> {
  final _map = MapController();
  bool _mapReady = false;
  Place? _pickup;
  Place? _drop;
  String _picking = 'drop';
  Map<String, dynamic>? _quote;
  String _car = 'sedan';
  Meta? _meta;
  String? _error;
  String? _notice = 'Finding your location…';
  bool _quoting = false;
  bool _booking = false;
  int _quoteSeq = 0;

  @override
  void initState() {
    super.initState();
    _locate();
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      try {
        final meta = await AuthScope.read(context).meta();
        if (mounted) setState(() => _meta = meta);
      } catch (_) {}
    });
  }

  Future<void> _locate() async {
    try {
      final here = await currentLocation();
      if (!mounted) return;
      setState(() {
        _notice = null;
        _pickup ??= Place(here, 'Current location');
      });
      _fit();
      final label = await reverseGeocode(here);
      if (mounted && _pickup?.point == here) setState(() => _pickup = _pickup!.withLabel(label));
      _getQuote();
    } catch (e) {
      if (mounted) {
        setState(() {
          _notice = errorText(e);
          _picking = 'pickup';
        });
      }
    }
  }

  void _fit() {
    if (!_mapReady) return;
    final pts = [_pickup?.point, _drop?.point].whereType<LatLng>().toList();
    if (pts.length == 1) _map.move(pts.first, 15);
    if (pts.length == 2) {
      _map.fitCamera(CameraFit.bounds(bounds: LatLngBounds.fromPoints(pts), padding: const EdgeInsets.all(56)));
    }
  }

  void _setPoint(String which, Place place) {
    setState(() {
      if (which == 'pickup') {
        _pickup = place;
        _picking = 'drop';
      } else {
        _drop = place;
      }
    });
    _fit();
    _getQuote();
  }

  Future<void> _pickOnMap(LatLng point) async {
    final which = _picking;
    _setPoint(which, Place(point, 'Looking up address…'));
    final label = await reverseGeocode(point);
    if (!mounted) return;
    setState(() {
      if (which == 'pickup' && _pickup?.point == point) _pickup = _pickup!.withLabel(label);
      if (which == 'drop' && _drop?.point == point) _drop = _drop!.withLabel(label);
    });
  }

  Future<void> _search(String which) async {
    final place = await showModalBottomSheet<Place>(
      context: context,
      isScrollControlled: true,
      builder: (_) => _SearchSheet(title: which == 'pickup' ? 'Pickup location' : 'Where to?'),
    );
    if (place != null) _setPoint(which, place);
  }

  Future<void> _getQuote() async {
    final p = _pickup, d = _drop;
    setState(() => _quote = null);
    if (p == null || d == null) return;
    final seq = ++_quoteSeq;
    setState(() {
      _quoting = true;
      _error = null;
    });
    try {
      final q = await AuthScope.read(context).api.post('/rider/quote/', {
        'pickup_lat': p.point.latitude,
        'pickup_lng': p.point.longitude,
        'drop_lat': d.point.latitude,
        'drop_lng': d.point.longitude,
      }) as Map<String, dynamic>;
      if (mounted && seq == _quoteSeq) setState(() => _quote = q);
    } catch (e) {
      if (mounted && seq == _quoteSeq) setState(() => _error = errorText(e));
    } finally {
      if (mounted && seq == _quoteSeq) setState(() => _quoting = false);
    }
  }

  Future<void> _book() async {
    final p = _pickup!, d = _drop!;
    setState(() {
      _booking = true;
      _error = null;
    });
    try {
      final json = await AuthScope.read(context).api.post('/rider/rides/', {
        'pickup': p.label,
        'drop': d.label,
        'car_type': _car,
        'pickup_lat': p.point.latitude,
        'pickup_lng': p.point.longitude,
        'drop_lat': d.point.latitude,
        'drop_lng': d.point.longitude,
      });
      final ride = Ride.fromJson(json as Map<String, dynamic>);
      if (!mounted) return;
      setState(() {
        _drop = null;
        _quote = null;
      });
      widget.onBooked?.call();
      await Navigator.of(context).push(MaterialPageRoute(builder: (_) => RideDetailScreen(rideId: ride.id, initial: ride)));
    } catch (e) {
      if (mounted) setState(() => _error = errorText(e));
    } finally {
      if (mounted) setState(() => _booking = false);
    }
  }

  List<LatLng> get _routeLine {
    final geometry = _quote?['geometry'] as List?;
    if (geometry != null && geometry.length >= 2) {
      return geometry.map((p) => LatLng(toDouble((p as List)[0]), toDouble(p[1]))).toList();
    }
    return [_pickup?.point, _drop?.point].whereType<LatLng>().toList();
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(title: const Text('Book a ride')),
      body: Column(children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 0, 12, 8),
          child: Column(children: [
            if (_notice != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Text(_notice!, style: const TextStyle(color: Colors.white60)),
              ),
            _PointTile(
              color: Colors.green,
              label: _pickup?.label ?? 'Choose pickup',
              active: _picking == 'pickup',
              onTap: () => _search('pickup'),
              onPinTap: () => setState(() => _picking = 'pickup'),
            ),
            const SizedBox(height: 6),
            _PointTile(
              color: Colors.redAccent,
              label: _drop?.label ?? 'Where to?',
              active: _picking == 'drop',
              onTap: () => _search('drop'),
              onPinTap: () => setState(() => _picking = 'drop'),
            ),
          ]),
        ),
        Expanded(
          child: Stack(children: [
            FlutterMap(
              mapController: _map,
              options: MapOptions(
                initialCenter: _kannur,
                initialZoom: 13,
                onMapReady: () {
                  _mapReady = true;
                  _fit();
                },
                onTap: (_, point) => _pickOnMap(point),
              ),
              children: [
                TileLayer(
                  urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                  userAgentPackageName: 'com.turbocab.turbo_rider',
                ),
                if (_pickup != null && _drop != null)
                  PolylineLayer(polylines: [Polyline(points: _routeLine, strokeWidth: 5, color: scheme.primary)]),
                MarkerLayer(markers: [
                  if (_pickup != null)
                    Marker(point: _pickup!.point, width: 40, height: 40, child: const Icon(Icons.trip_origin, color: Colors.green, size: 30)),
                  if (_drop != null)
                    Marker(
                      point: _drop!.point,
                      width: 40,
                      height: 40,
                      alignment: Alignment.topCenter,
                      child: const Icon(Icons.location_on, color: Colors.redAccent, size: 40),
                    ),
                ]),
                const RichAttributionWidget(attributions: [TextSourceAttribution('OpenStreetMap contributors')]),
              ],
            ),
            Positioned(
              top: 8,
              left: 8,
              child: Chip(label: Text('Tap map to set ${_picking == 'pickup' ? 'pickup' : 'drop'}')),
            ),
            Positioned(
              right: 12,
              bottom: 12,
              child: FloatingActionButton.small(
                heroTag: 'locate',
                onPressed: _locate,
                tooltip: 'Use my location',
                child: const Icon(Icons.my_location),
              ),
            ),
          ]),
        ),
        _BottomPanel(
          error: _error,
          quoting: _quoting,
          quote: _quote,
          meta: _meta,
          car: _car,
          booking: _booking,
          onCar: (c) => setState(() => _car = c),
          onBook: _book,
        ),
      ]),
    );
  }
}

class _PointTile extends StatelessWidget {
  const _PointTile({required this.color, required this.label, required this.active, required this.onTap, required this.onPinTap});

  final Color color;
  final String label;
  final bool active;
  final VoidCallback onTap;
  final VoidCallback onPinTap;

  @override
  Widget build(BuildContext context) => Material(
        color: const Color(0xFF1F1F23),
        borderRadius: BorderRadius.circular(10),
        child: InkWell(
          borderRadius: BorderRadius.circular(10),
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.only(left: 12),
            child: Row(children: [
              Icon(Icons.circle, size: 12, color: color),
              const SizedBox(width: 10),
              Expanded(child: Text(label, maxLines: 1, overflow: TextOverflow.ellipsis)),
              IconButton(
                tooltip: 'Set on map',
                onPressed: onPinTap,
                icon: Icon(Icons.push_pin, color: active ? Theme.of(context).colorScheme.primary : Colors.white38),
              ),
            ]),
          ),
        ),
      );
}

class _BottomPanel extends StatelessWidget {
  const _BottomPanel({
    required this.error,
    required this.quoting,
    required this.quote,
    required this.meta,
    required this.car,
    required this.booking,
    required this.onCar,
    required this.onBook,
  });

  final String? error;
  final bool quoting;
  final Map<String, dynamic>? quote;
  final Meta? meta;
  final String car;
  final bool booking;
  final ValueChanged<String> onCar;
  final VoidCallback onBook;

  @override
  Widget build(BuildContext context) {
    final fares = (quote?['fares'] as Map?) ?? const {};
    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          ErrorBanner(error),
          if (quoting) const Padding(padding: EdgeInsets.all(8), child: LinearProgressIndicator()),
          if (quote != null) ...[
            Text(
              '${quote!['distance_km']} km${quote!['source'] == 'estimate' ? ' (estimated)' : ''}',
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 8),
            SizedBox(
              height: 76,
              child: ListView(
                scrollDirection: Axis.horizontal,
                children: [
                  for (final c in meta?.carTypes ?? const <Choice>[])
                    Padding(
                      padding: const EdgeInsets.only(right: 8),
                      child: ChoiceChip(
                        selected: car == c.value,
                        onSelected: (_) => onCar(c.value),
                        label: Column(mainAxisSize: MainAxisSize.min, children: [
                          Text(c.label),
                          Text(money(toDouble(fares[c.value])), style: const TextStyle(fontWeight: FontWeight.w700)),
                        ]),
                      ),
                    ),
                ],
              ),
            ),
            const SizedBox(height: 8),
            FilledButton(
              onPressed: booking ? null : onBook,
              style: FilledButton.styleFrom(padding: const EdgeInsets.symmetric(vertical: 14)),
              child: Text(booking ? 'Booking…' : 'Confirm booking · ${money(toDouble(fares[car]))}'),
            ),
          ] else if (!quoting && error == null)
            const Text('Choose a pickup and drop to see fares.', textAlign: TextAlign.center, style: TextStyle(color: Colors.white54)),
        ]),
      ),
    );
  }
}

class _SearchSheet extends StatefulWidget {
  const _SearchSheet({required this.title});

  final String title;

  @override
  State<_SearchSheet> createState() => _SearchSheetState();
}

class _SearchSheetState extends State<_SearchSheet> {
  final _text = TextEditingController();
  Timer? _debounce;
  List<Place> _results = const [];
  String? _status;

  @override
  void dispose() {
    _debounce?.cancel();
    _text.dispose();
    super.dispose();
  }

  void _onChanged(String q) {
    _debounce?.cancel();
    if (q.trim().length < 3) {
      setState(() {
        _results = const [];
        _status = null;
      });
      return;
    }
    _debounce = Timer(const Duration(milliseconds: 450), () async {
      setState(() => _status = 'Searching…');
      try {
        final r = await searchPlaces(q.trim());
        if (mounted) {
          setState(() {
            _results = r;
            _status = r.isEmpty ? 'No places found.' : null;
          });
        }
      } catch (_) {
        if (mounted) setState(() => _status = 'Search failed. Check your connection.');
      }
    });
  }

  @override
  Widget build(BuildContext context) => Padding(
        padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
        child: SizedBox(
          height: MediaQuery.of(context).size.height * 0.7,
          child: Column(children: [
            Padding(
              padding: const EdgeInsets.all(16),
              child: TextField(
                controller: _text,
                autofocus: true,
                onChanged: _onChanged,
                decoration: InputDecoration(
                  labelText: widget.title,
                  prefixIcon: const Icon(Icons.search),
                  border: const OutlineInputBorder(),
                ),
              ),
            ),
            if (_status != null) Padding(padding: const EdgeInsets.all(8), child: Text(_status!, style: const TextStyle(color: Colors.white54))),
            Expanded(
              child: ListView.builder(
                itemCount: _results.length,
                itemBuilder: (context, i) => ListTile(
                  leading: const Icon(Icons.place_outlined),
                  title: Text(_results[i].label, maxLines: 2, overflow: TextOverflow.ellipsis),
                  onTap: () => Navigator.pop(context, _results[i]),
                ),
              ),
            ),
          ]),
        ),
      );
}
