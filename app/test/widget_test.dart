// Lean unit tests for pure logic (without the map's platform channels).
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:heritage_at_risk/map/route_service.dart';
import 'package:heritage_at_risk/theme.dart';
import 'package:maplibre_gl/maplibre_gl.dart' show LatLng;

void main() {
  test('threat colour follows the inverted traffic-light ramp', () {
    expect(AppColors.forThreatLevel('high'), AppColors.threatHigh);
    expect(AppColors.forThreatLevel('medium'), AppColors.threatMedium);
    expect(AppColors.forThreatLevel('low'), AppColors.threatLow);
    // An unknown level falls back to "low".
    expect(AppColors.forThreatLevel('unknown'), AppColors.threatLow);
  });

  test('threat label maps level keys to English', () {
    expect(AppColors.threatLabel('high'), 'high');
    expect(AppColors.threatLabel('medium'), 'medium');
    expect(AppColors.threatLabel('low'), 'low');
    expect(AppColors.threatLabel('unknown'), 'low');
  });

  test('light theme builds without error (design is light-only)', () {
    expect(AppTheme.light().brightness, Brightness.light);
  });

  test('route result serialises to a GeoJSON LineString (lon/lat order)', () {
    const route = RouteResult(
      points: [LatLng(33.5, 36.3), LatLng(34.55, 38.28)],
      distanceMetres: 215000,
      durationSeconds: 9000,
      profile: RouteProfile.drive,
    );
    final geojson = route.toGeojson();
    final feature = (geojson['features'] as List).single as Map;
    final geometry = feature['geometry'] as Map;
    expect(geometry['type'], 'LineString');
    // GeoJSON stores [lon, lat]; LatLng carries (lat, lon). LatLng normalises
    // the longitude, which can introduce float noise, hence closeTo.
    final coords = geometry['coordinates'] as List;
    expect(coords, hasLength(2));
    expect((coords[0] as List)[0], closeTo(36.3, 1e-9));
    expect((coords[0] as List)[1], closeTo(33.5, 1e-9));
    expect((coords[1] as List)[0], closeTo(38.28, 1e-9));
    expect((coords[1] as List)[1], closeTo(34.55, 1e-9));
  });

  test('routing is disabled without a build-time ORS key', () {
    // Tests run without --dart-define, so the key must be absent and the
    // service must report itself unconfigured (the UI then explains setup).
    expect(RouteService.isConfigured, isFalse);
  });
}
