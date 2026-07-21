import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:maplibre_gl/maplibre_gl.dart';

/// Routing profiles offered in the app (a subset of ORS profiles).
enum RouteProfile {
  drive('driving-car', 'Drive'),
  walk('foot-walking', 'Walk');

  const RouteProfile(this.orsId, this.label);

  /// Profile id in the ORS directions URL.
  final String orsId;
  final String label;
}

/// A fetched route: the line geometry plus its summary numbers.
class RouteResult {
  const RouteResult({
    required this.points,
    required this.distanceMetres,
    required this.durationSeconds,
    required this.profile,
  });

  final List<LatLng> points;
  final double distanceMetres;
  final double durationSeconds;
  final RouteProfile profile;

  /// Route line as a GeoJSON FeatureCollection for a MapLibre source.
  Map<String, dynamic> toGeojson() => {
        'type': 'FeatureCollection',
        'features': [
          {
            'type': 'Feature',
            'properties': const <String, dynamic>{},
            'geometry': {
              'type': 'LineString',
              'coordinates': [
                for (final p in points) [p.longitude, p.latitude],
              ],
            },
          },
        ],
      };
}

/// Thrown with a user-presentable message when routing fails.
class RouteException implements Exception {
  const RouteException(this.message);

  final String message;

  @override
  String toString() => message;
}

/// Directions client for the OpenRouteService API (v2, GeoJSON responses).
///
/// The API key is injected at build time via
/// `--dart-define=ORS_API_KEY=...` and is never committed to the repo.
/// Without a key the routing UI stays visible but explains how to enable it.
class RouteService {
  static const String _apiKey = String.fromEnvironment('ORS_API_KEY');
  static const String _baseUrl =
      'https://api.openrouteservice.org/v2/directions';

  /// Whether a key was baked into this build.
  static bool get isConfigured => _apiKey.isNotEmpty;

  /// Fetch a route between two coordinates. Throws [RouteException] with a
  /// short, user-readable message on any failure.
  static Future<RouteResult> fetchRoute({
    required LatLng from,
    required LatLng to,
    required RouteProfile profile,
  }) async {
    if (!isConfigured) {
      throw const RouteException(
        'Routing is not configured (build with --dart-define=ORS_API_KEY=...).',
      );
    }
    final uri = Uri.parse('$_baseUrl/${profile.orsId}/geojson');
    http.Response response;
    try {
      response = await http
          .post(
            uri,
            headers: {
              'Authorization': _apiKey,
              'Content-Type': 'application/json',
            },
            body: jsonEncode({
              'coordinates': [
                [from.longitude, from.latitude],
                [to.longitude, to.latitude],
              ],
            }),
          )
          .timeout(const Duration(seconds: 20));
    } catch (_) {
      throw const RouteException('Routing request failed (network).');
    }
    if (response.statusCode == 404) {
      // ORS answers 404 when no route exists between the points (e.g. across
      // water or outside the road network), not only for bad URLs.
      throw const RouteException('No route found between you and this site.');
    }
    if (response.statusCode != 200) {
      throw RouteException('Routing service error (${response.statusCode}).');
    }

    final body = jsonDecode(response.body) as Map<String, dynamic>;
    final features = (body['features'] as List?) ?? const [];
    if (features.isEmpty) {
      throw const RouteException('No route found between you and this site.');
    }
    final feature = features.first as Map<String, dynamic>;
    final coords =
        ((feature['geometry'] as Map?)?['coordinates'] as List?) ?? const [];
    final summary =
        ((feature['properties'] as Map?)?['summary'] as Map?) ?? const {};
    final points = <LatLng>[
      for (final c in coords)
        if (c is List && c.length >= 2)
          LatLng((c[1] as num).toDouble(), (c[0] as num).toDouble()),
    ];
    if (points.length < 2) {
      throw const RouteException('Routing service returned no geometry.');
    }
    return RouteResult(
      points: points,
      distanceMetres: ((summary['distance'] as num?) ?? 0).toDouble(),
      durationSeconds: ((summary['duration'] as num?) ?? 0).toDouble(),
      profile: profile,
    );
  }
}
