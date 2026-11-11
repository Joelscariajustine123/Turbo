import 'dart:convert';

import 'package:geolocator/geolocator.dart';
import 'package:http/http.dart' as http;
import 'package:latlong2/latlong.dart';

/// A point on the map with a readable address.
class Place {
  const Place(this.point, this.label);

  final LatLng point;
  final String label;

  Place withLabel(String l) => Place(point, l);
}

const _nominatim = 'https://nominatim.openstreetmap.org';
// Nominatim's usage policy asks apps to identify themselves.
const _headers = {'User-Agent': 'TurboCab-Rider/1.0', 'Accept-Language': 'en'};

String _coords(LatLng p) => '${p.latitude.toStringAsFixed(5)}, ${p.longitude.toStringAsFixed(5)}';

Future<List<Place>> searchPlaces(String query) async {
  final uri = Uri.parse('$_nominatim/search').replace(queryParameters: {
    'format': 'json',
    'limit': '8',
    'countrycodes': 'in',
    'q': query,
  });
  final res = await http.get(uri, headers: _headers).timeout(const Duration(seconds: 15));
  if (res.statusCode != 200) throw Exception('Search failed');
  final rows = jsonDecode(utf8.decode(res.bodyBytes)) as List;
  return rows
      .map((r) => Place(
            LatLng(double.parse(r['lat'].toString()), double.parse(r['lon'].toString())),
            r['display_name'].toString(),
          ))
      .toList();
}

Future<String> reverseGeocode(LatLng p) async {
  try {
    final uri = Uri.parse('$_nominatim/reverse').replace(queryParameters: {
      'format': 'json',
      'lat': '${p.latitude}',
      'lon': '${p.longitude}',
    });
    final res = await http.get(uri, headers: _headers).timeout(const Duration(seconds: 15));
    final data = jsonDecode(utf8.decode(res.bodyBytes)) as Map<String, dynamic>;
    return (data['display_name'] as String?) ?? _coords(p);
  } catch (_) {
    return _coords(p);
  }
}

/// Current GPS position, asking for permission if needed.
Future<LatLng> currentLocation() async {
  if (!await Geolocator.isLocationServiceEnabled()) {
    throw Exception('Location is turned off. Turn it on or search for your pickup.');
  }
  var permission = await Geolocator.checkPermission();
  if (permission == LocationPermission.denied) {
    permission = await Geolocator.requestPermission();
  }
  if (permission == LocationPermission.denied || permission == LocationPermission.deniedForever) {
    throw Exception('Location permission was denied. Search for your pickup instead.');
  }
  final pos = await Geolocator.getCurrentPosition();
  return LatLng(pos.latitude, pos.longitude);
}

String upiLink(String upiId, double amount, int rideId) => Uri(
      scheme: 'upi',
      host: 'pay',
      queryParameters: {
        'pa': upiId,
        'pn': 'Turbo Cabs',
        'am': amount.toStringAsFixed(2),
        'tn': 'Ride-$rideId',
        'cu': 'INR',
      },
    ).toString();
