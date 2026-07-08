import 'dart:convert';
import 'dart:math' show Point;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show rootBundle;
import 'package:geolocator/geolocator.dart';
import 'package:maplibre_gl/maplibre_gl.dart';

import '../basemap.dart';
import '../theme.dart';
import 'info_sheet.dart';
import 'conflict_event_sheet.dart';
import 'conflict_overview_sheet.dart';
import 'model_3d_sheet.dart';
import 'pleiades_sheet.dart';
import 'route_service.dart';
import 'site_detail_sheet.dart';
import 'site_list_screen.dart';
import 'threat_legend.dart';

/// The two views of the map, switched by a segmented button at the top.
///
/// Both share ONE MapLibre instance (one GL context); switching only toggles
/// which layer set and which explanatory panel are shown. Two live maps would
/// be memory-heavy and crash-prone on Android, so we deliberately reuse one.
enum MapMode {
  /// Threat score per site plus heritage context (Pleiades, density, 3D).
  threat,

  /// Only the conflict data: UCDP events and the 30 km radius.
  conflict,
}

/// Main view: the threat map of the MENA region.
///
/// Reads the bundled pipeline artefacts and stacks them as MapLibre layers over
/// a monochrome CARTO basemap: the scored sites as an inverted traffic-light
/// ramp (on top), ancient places and building density as progressive context
/// (below). Context layers appear only when zooming in. A segmented button
/// switches to a conflict-only view of the same map.
class MapScreen extends StatefulWidget {
  const MapScreen({
    super.key,
    required this.isDark,
    required this.onToggleTheme,
  });

  final bool isDark;
  final VoidCallback onToggleTheme;

  @override
  State<MapScreen> createState() => _MapScreenState();
}

class _MapScreenState extends State<MapScreen> {
  static const String _sitesSource = 'sites';
  static const String _sitesLayer = 'sites-circles';
  static const String _sitesPlainLayer = 'sites-plain-circles';
  static const String _pleiadesSource = 'pleiades';
  static const String _pleiadesLayer = 'pleiades-circles';
  static const String _densitySource = 'density';
  static const String _densityLayer = 'density-heat';
  static const String _models3dSource = 'models3d';
  static const String _models3dLayer = 'models3d-circles';
  static const String _radiusSource = 'conflict-radius';
  static const String _radiusLayer = 'conflict-radius-line';
  static const String _eventsSource = 'conflict-events';
  static const String _eventsLayer = 'conflict-events-circles';
  static const String _routeSource = 'route';
  static const String _routeCasingLayer = 'route-casing';
  static const String _routeLayer = 'route-line';

  static const Map<String, dynamic> _emptyGeojson = {
    'type': 'FeatureCollection',
    'features': <dynamic>[],
  };

  MapLibreMapController? _controller;

  Map<String, dynamic>? _sitesGeojson;
  Map<String, dynamic>? _pleiadesGeojson;
  Map<String, dynamic>? _densityGeojson;
  Map<String, dynamic>? _models3dGeojson;
  Map<String, dynamic>? _radiusGeojson;
  Map<String, dynamic>? _eventsGeojson;

  MapMode _mode = MapMode.threat;

  final Set<String> _activeLevels = {'high', 'medium', 'low'};
  bool _showPleiades = true;
  bool _showDensity = true;
  bool _showBuildings = true;
  bool _showModels3d = true;
  bool _showRadius = false;
  bool _showEvents = false;
  // Whether the info panel below the mode switch is expanded (the switch itself
  // always stays visible so the user can change views).
  bool _topInfoExpanded = true;
  int _siteCount = 0;
  int _inDangerCount = 0;
  int _totalConflictEvents = 0;
  int _conflictSiteCount = 0;

  /// Foreground location: the device-location dot is shown once the user grants
  /// permission via the locate button. Off until then (no passive tracking).
  bool _myLocationEnabled = false;
  bool _locating = false;
  _NearestSite? _nearest;

  /// Active route (ORS directions): result, destination and busy flag. The
  /// destination is kept so the profile switch can re-request the same route.
  RouteResult? _route;
  _RouteTarget? _routeTarget;
  bool _routingBusy = false;

  /// Building layers of the provider basemap (resolved from the style at runtime).
  final Set<String> _buildingLayerIds = {};

  Future<Map<String, dynamic>> _loadGeojson(String asset) async {
    final raw = await rootBundle.loadString(asset);
    return jsonDecode(raw) as Map<String, dynamic>;
  }

  Future<void> _ensureDataLoaded() async {
    _sitesGeojson ??= await _loadGeojson('assets/data/sites.geojson');
    _pleiadesGeojson ??= await _loadGeojson('assets/data/pleiades.geojson');
    _densityGeojson ??= await _loadGeojson(
      'assets/data/building_density.geojson',
    );
    _models3dGeojson ??= await _loadGeojson('assets/data/heritage_3d.geojson');
    _radiusGeojson ??= await _loadGeojson('assets/data/conflict_radius.geojson');
    _eventsGeojson ??= await _loadGeojson('assets/data/conflict_events.geojson');
    final features = (_sitesGeojson!['features'] as List?) ?? const [];
    final count = features.length;
    final inDanger = features
        .where((f) => (f as Map)['properties']?['in_danger'] == true)
        .length;
    // Conflict overview tallies: total georeferenced UCDP events near sites and
    // how many sites have at least one event in their radius.
    final totalEvents = ((_eventsGeojson?['features'] as List?) ?? const []).length;
    final conflictSites = features
        .where((f) => ((f as Map)['properties']?['conflict_count'] ?? 0) is num
            ? ((f['properties']['conflict_count'] ?? 0) as num) > 0
            : false)
        .length;
    if (mounted) {
      setState(() {
        _siteCount = count;
        _inDangerCount = inDanger;
        _totalConflictEvents = totalEvents;
        _conflictSiteCount = conflictSites;
      });
    }
  }

  Future<void> _onStyleLoaded() async {
    final controller = _controller;
    if (controller == null) return;
    await _ensureDataLoaded();

    // Building density as a warm heatmap "shading" (bottom, from mid zoom).
    await controller.addGeoJsonSource(_densitySource, _densityGeojson!);
    await controller.addHeatmapLayer(
      _densitySource,
      _densityLayer,
      HeatmapLayerProperties(
        heatmapWeight: [
          'interpolate',
          ['linear'],
          ['get', 'w'],
          0,
          0.0,
          328,
          1.0,
        ],
        heatmapIntensity: [
          'interpolate',
          ['linear'],
          ['zoom'],
          6,
          0.6,
          14,
          1.4,
        ],
        heatmapRadius: [
          'interpolate',
          ['linear'],
          ['zoom'],
          6,
          6.0,
          12,
          22.0,
        ],
        heatmapColor: [
          'interpolate',
          ['linear'],
          ['heatmap-density'],
          0.0,
          'rgba(0,0,0,0)',
          0.2,
          'rgba(254,224,144,0.45)',
          0.4,
          'rgb(253,174,97)',
          0.7,
          'rgb(244,109,67)',
          1.0,
          'rgb(178,24,43)',
        ],
        heatmapOpacity: [
          'interpolate',
          ['linear'],
          ['zoom'],
          6,
          0.0,
          7,
          0.65,
          14,
          0.6,
          16,
          0.0,
        ],
      ),
      minzoom: 6.0,
    );

    // Ancient places (Pleiades) as quiet context, deliberately outside the ramp.
    // Interactive so a tap opens the Pleiades info sheet.
    await controller.addGeoJsonSource(_pleiadesSource, _pleiadesGeojson!);
    await controller.addCircleLayer(
      _pleiadesSource,
      _pleiadesLayer,
      const CircleLayerProperties(
        circleColor: '#5B4FC4',
        circleRadius: [
          'interpolate',
          ['linear'],
          ['zoom'],
          6,
          2.5,
          9,
          5.0,
          13,
          8.5,
        ],
        circleOpacity: 0.78,
        circleStrokeColor: '#ffffff',
        circleStrokeWidth: 0.6,
      ),
      minzoom: 6.0,
    );

    // Conflict-evaluation radius per site (below the markers): dashed outlines of
    // the geographic circle in which the conflict component counts UCDP events.
    // Off by default; a transparency overlay the user can toggle on.
    await controller.addGeoJsonSource(_radiusSource, _radiusGeojson!);
    await controller.addLineLayer(
      _radiusSource,
      _radiusLayer,
      const LineLayerProperties(
        lineColor: '#D85A30',
        lineWidth: 1.5,
        lineOpacity: 0.7,
        lineDasharray: [2, 2],
      ),
      // Non-interactive: an interactive line layer swallows nearby taps
      // (feature#onTap fires instead of map#onMapClick), which blocked the
      // conflict-event tap sheet anywhere near a radius outline.
      enableInteraction: false,
    );

    // Route line (ORS directions) below the markers: white casing plus a strong
    // blue line, deliberately outside both the threat ramp and the event reds.
    // The source starts empty and is filled when the user requests a route; it
    // survives a style reload (theme switch) via the kept _route state.
    await controller.addGeoJsonSource(
      _routeSource,
      _route?.toGeojson() ?? _emptyGeojson,
    );
    await controller.addLineLayer(
      _routeSource,
      _routeCasingLayer,
      const LineLayerProperties(
        lineColor: '#ffffff',
        lineWidth: [
          'interpolate',
          ['linear'],
          ['zoom'],
          5,
          5.0,
          12,
          9.0,
        ],
        lineOpacity: 0.9,
        lineCap: 'round',
        lineJoin: 'round',
      ),
      enableInteraction: false,
    );
    await controller.addLineLayer(
      _routeSource,
      _routeLayer,
      const LineLayerProperties(
        lineColor: '#2166AC',
        lineWidth: [
          'interpolate',
          ['linear'],
          ['zoom'],
          5,
          3.0,
          12,
          5.5,
        ],
        lineOpacity: 0.95,
        lineCap: 'round',
        lineJoin: 'round',
      ),
      enableInteraction: false,
    );

    // The scored sites as the threat hero (on top). Colour from the data,
    // radius additionally by score; white stroke for contrast.
    await controller.addGeoJsonSource(_sitesSource, _sitesGeojson!);
    await controller.addCircleLayer(
      _sitesSource,
      _sitesLayer,
      const CircleLayerProperties(
        circleColor: ['get', 'threat_color'],
        circleRadius: [
          'interpolate',
          ['linear'],
          ['get', 'total_score'],
          0,
          5.0,
          6,
          9.0,
          10,
          13.0,
        ],
        circleOpacity: 0.95,
        circleStrokeColor: '#ffffff',
        circleStrokeWidth: 1.4,
      ),
    );

    // Plain site markers for the conflict view: same locations, but a neutral
    // sandstone dot WITHOUT the threat ramp (the conflict view is about the
    // conflict data, not the score). Small and non-interactive; only a location
    // reference. Shown only in conflict mode (see _applyModeVisibility).
    await controller.addCircleLayer(
      _sitesSource,
      _sitesPlainLayer,
      CircleLayerProperties(
        circleColor: AppColors.sandstoneHex,
        circleRadius: 4.0,
        circleOpacity: 0.9,
        circleStrokeColor: '#ffffff',
        circleStrokeWidth: 1.2,
      ),
      enableInteraction: false,
    );

    // UCDP conflict events as bold dots, coloured by event year (two-step red
    // ramp: current year dark, previous year lighter; the rolling 12-month
    // window spans exactly these two). Added AFTER the site markers so in the
    // conflict view they sit ABOVE the (plain) sites — the conflict data is the
    // hero there. Larger and more opaque at low zoom so the pattern reads in
    // the overview. Off by default in threat view, non-interactive (taps run
    // via _onMapClick).
    await controller.addGeoJsonSource(_eventsSource, _eventsGeojson!);
    await controller.addCircleLayer(
      _eventsSource,
      _eventsLayer,
      CircleLayerProperties(
        circleColor: [
          'match',
          ['get', 'year'],
          DateTime.now().year,
          AppColors.eventYearCurrentHex,
          AppColors.eventYearPreviousHex,
        ],
        circleRadius: [
          'interpolate',
          ['linear'],
          ['zoom'],
          4,
          4.5,
          9,
          6.5,
          13,
          8.0,
        ],
        circleOpacity: 0.88,
        circleStrokeColor: AppColors.eventStrokeHex,
        circleStrokeWidth: 0.9,
      ),
      // Non-interactive on purpose: with ~41k points, registering this layer for
      // MapLibre's per-gesture hit test froze the UI thread. We handle event taps
      // cheaply in _onMapClick instead (a small queryRenderedFeatures rect).
      enableInteraction: false,
    );

    // 3D-model markers on top: a cyan fill with a white ring (matching the
    // sites' white stroke), set apart from the threat ramp and Pleiades by
    // colour. Interactive (tap opens the sheet).
    await controller.addGeoJsonSource(_models3dSource, _models3dGeojson!);
    await controller.addCircleLayer(
      _models3dSource,
      _models3dLayer,
      const CircleLayerProperties(
        circleColor: '#0FB5C9',
        circleRadius: [
          'interpolate',
          ['linear'],
          ['zoom'],
          4,
          4.0,
          9,
          6.5,
          13,
          9.0,
        ],
        circleStrokeColor: '#ffffff',
        circleStrokeWidth: 1.4,
        circleOpacity: 0.95,
      ),
    );

    await _applyThreatFilter();
    await controller.setLayerVisibility(_sitesLayer, _mode == MapMode.threat);
    await controller.setLayerVisibility(_sitesPlainLayer, _mode == MapMode.conflict);
    await controller.setLayerVisibility(_pleiadesLayer, _showPleiades);
    await controller.setLayerVisibility(_densityLayer, _showDensity);
    await controller.setLayerVisibility(_models3dLayer, _showModels3d);
    await controller.setLayerVisibility(_radiusLayer, _showRadius);
    await controller.setLayerVisibility(_eventsLayer, _showEvents);
    await _styleBasemapBuildings();
  }

  /// Tint the CARTO basemap building layers warm (ember logic, matching the
  /// density shading) and show or hide them per the toggle. We deliberately do
  /// not ship our own footprints; the geometry comes from the basemap. Runs on
  /// every style load (including after the light/dark switch).
  Future<void> _styleBasemapBuildings() async {
    final controller = _controller;
    if (controller == null) return;
    final ids = await controller.getLayerIds();
    _buildingLayerIds
      ..clear()
      ..addAll(
        ids.whereType<String>().where(
          (id) => id.toLowerCase().contains('building'),
        ),
      );
    final warm = widget.isDark
        ? AppColors.buildingWarmDarkHex
        : AppColors.buildingWarmLightHex;
    for (final id in _buildingLayerIds) {
      // Defensive per layer: not every "building" layer is a fill layer.
      try {
        await controller.setLayerProperties(
          id,
          FillLayerProperties(fillColor: warm, fillOpacity: 0.9),
        );
        await controller.setLayerVisibility(id, _showBuildings);
      } catch (_) {
        // Skip layers without a fill paint (e.g. extrusion/symbol).
      }
    }
  }

  Future<void> _applyThreatFilter() async {
    final controller = _controller;
    if (controller == null) return;
    await controller.setFilter(_sitesLayer, [
      'in',
      ['get', 'threat_level'],
      ['literal', _activeLevels.toList()],
    ]);
  }

  /// Tap on an interactive feature. MapLibre Native does the hit test itself and
  /// fires `onFeatureTapped` (not `onMapClick`) for interactive layers such as
  /// the sites and Pleiades places; we route each to its own detail sheet.
  void _onFeatureTapped(
    Point<double> point,
    LatLng latLng,
    String id,
    String layerId,
    Annotation? annotation,
  ) {
    if (layerId == _sitesLayer) {
      _showDetailAt(point, _sitesLayer);
    } else if (layerId == _pleiadesLayer) {
      _showDetailAt(point, _pleiadesLayer);
    } else if (layerId == _models3dLayer) {
      _showDetailAt(point, _models3dLayer);
    }
  }

  /// Generic map tap (fires only when no interactive feature was hit). Used to
  /// pick up the non-interactive conflict-event dots: we query just a small rect
  /// around the tap against the events layer, so there is no per-gesture cost.
  ///
  /// The screen point is deliberately re-derived from the geographic coordinate
  /// via toScreenLocation: the point delivered by onMapClick is not in the same
  /// pixel space as queryRenderedFeaturesInRect on Android (logical vs physical
  /// pixels), which made event taps miss on the device.
  Future<void> _onMapClick(Point<double> point, LatLng latLng) async {
    final controller = _controller;
    if (!_showEvents || controller == null) return;
    final screen = await controller.toScreenLocation(latLng);
    await _showDetailAt(
      Point(screen.x.toDouble(), screen.y.toDouble()),
      _eventsLayer,
    );
  }

  Future<void> _showDetailAt(Point<double> point, String layerId) async {
    final controller = _controller;
    if (controller == null) return;
    // Small rectangle around the tap (tolerance instead of a single pixel) on
    // the given layer. Coordinates are physical device pixels, so the finger
    // tolerance (~16 logical px) is scaled by the device pixel ratio.
    final tolerance = 16.0 * MediaQuery.of(context).devicePixelRatio;
    final rect = Rect.fromCenter(
      center: Offset(point.x, point.y),
      width: tolerance,
      height: tolerance,
    );
    final features = await controller.queryRenderedFeaturesInRect(rect, [
      layerId,
    ], null);
    if (features.isEmpty || !mounted) return;
    final feature = _extractFeature(features.first);
    final properties = _extractProperties(feature);
    if (properties == null) return;
    // Target coordinates for the "Route here" action (from the tapped
    // feature's point geometry; the sheets themselves only see properties).
    // Routable: scored sites, Pleiades places and 3D-model markers — the
    // latter two make intra-site walking routes possible (e.g. from the
    // Palmyra entrance to a single monument). Conflict events are not
    // navigation targets.
    final coords =
        ((feature?['geometry'] as Map?)?['coordinates'] as List?) ?? const [];
    final nameKey = layerId == _pleiadesLayer ? 'title' : 'name';
    final target = layerId != _eventsLayer && coords.length >= 2
        ? _RouteTarget(
            name: '${properties[nameKey] ?? 'Destination'}',
            lat: (coords[1] as num).toDouble(),
            lon: (coords[0] as num).toDouble(),
          )
        : null;
    void Function()? onRoute(BuildContext sheetContext) => target == null
        ? null
        : () {
            Navigator.of(sheetContext).pop();
            _routeToSite(target, _route?.profile ?? RouteProfile.drive);
          };
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: false,
      builder: (sheetContext) {
        if (layerId == _pleiadesLayer) {
          return PleiadesSheet(
            properties: properties,
            onRoute: onRoute(sheetContext),
          );
        }
        if (layerId == _models3dLayer) {
          return Model3DSheet(
            properties: properties,
            onRoute: onRoute(sheetContext),
          );
        }
        if (layerId == _eventsLayer) {
          return ConflictEventSheet(properties: properties);
        }
        return SiteDetailSheet(
          properties: properties,
          onRoute: onRoute(sheetContext),
        );
      },
    );
  }

  /// Decode a query result into the full feature map (properties + geometry).
  Map<String, dynamic>? _extractFeature(dynamic feature) {
    var decoded = feature;
    if (decoded is String) decoded = jsonDecode(decoded);
    if (decoded is! Map) return null;
    return Map<String, dynamic>.from(decoded);
  }

  Map<String, dynamic>? _extractProperties(dynamic feature) {
    var decoded = feature;
    if (decoded is String) decoded = jsonDecode(decoded);
    if (decoded is! Map) return null;
    final props = decoded['properties'];
    if (props is Map) return Map<String, dynamic>.from(props);
    return Map<String, dynamic>.from(decoded);
  }

  void _toggleLevel(ThreatLevel level) {
    setState(() {
      if (!_activeLevels.remove(level.key)) _activeLevels.add(level.key);
    });
    _applyThreatFilter();
  }

  void _togglePleiades(bool show) {
    setState(() => _showPleiades = show);
    _controller?.setLayerVisibility(_pleiadesLayer, show);
  }

  void _toggleDensity(bool show) {
    setState(() => _showDensity = show);
    _controller?.setLayerVisibility(_densityLayer, show);
  }

  void _toggleBuildings(bool show) {
    setState(() => _showBuildings = show);
    for (final id in _buildingLayerIds) {
      _controller?.setLayerVisibility(id, show);
    }
  }

  void _toggleModels3d(bool show) {
    setState(() => _showModels3d = show);
    _controller?.setLayerVisibility(_models3dLayer, show);
  }

  void _toggleRadius(bool show) {
    setState(() => _showRadius = show);
    _controller?.setLayerVisibility(_radiusLayer, show);
  }

  void _toggleEvents(bool show) {
    setState(() => _showEvents = show);
    _controller?.setLayerVisibility(_eventsLayer, show);
  }

  /// Open the conflict overview: total events and the per-site breakdown,
  /// sorted by event count. Reads the already-loaded site scores.
  void _showConflictOverview() {
    final features = (_sitesGeojson?['features'] as List?) ?? const [];
    final sites = <ConflictSiteTally>[];
    for (final f in features) {
      final props = (f as Map)['properties'] as Map? ?? const {};
      final count = (props['conflict_count'] ?? 0);
      final events = count is num ? count.toInt() : 0;
      if (events <= 0) continue;
      sites.add(ConflictSiteTally(
        name: '${props['name'] ?? '—'}',
        countryIso2: '${props['country_iso2'] ?? ''}',
        events: events,
        threatLevel: '${props['threat_level'] ?? ''}',
      ));
    }
    sites.sort((a, b) => b.events.compareTo(a.events));
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (_) => ConflictOverviewSheet(
        totalEvents: _totalConflictEvents,
        siteCount: _conflictSiteCount,
        sites: sites,
      ),
    );
  }

  /// Open the country list; if the user taps a row, recentre the map on that
  /// site so the list works as a text index into the map.
  Future<void> _openSiteList() async {
    final target = await Navigator.of(context).push<({double lat, double lon})>(
      MaterialPageRoute<({double lat, double lon})>(
        builder: (_) => const SiteListScreen(),
      ),
    );
    if (target == null) return;
    await _controller?.animateCamera(
      CameraUpdate.newLatLngZoom(LatLng(target.lat, target.lon), 9.5),
    );
  }

  /// Switch between the threat and conflict views. Resets each view's layer set
  /// to its sensible default (the user can still toggle within a view), then
  /// applies the visibilities to the single shared map.
  void _setMode(MapMode mode) {
    if (mode == _mode) return;
    setState(() {
      _mode = mode;
      final conflict = mode == MapMode.conflict;
      // Conflict view: only the conflict layers; heritage context off.
      _showRadius = conflict;
      _showEvents = conflict;
      _showPleiades = !conflict;
      _showDensity = !conflict;
      _showBuildings = !conflict;
      _showModels3d = !conflict;
    });
    _applyModeVisibility();
  }

  /// Apply the current mode's layer visibilities to the map. The scored sites
  /// belong to the threat view; the radius outlines already show where the sites
  /// are in the conflict view, so no marker context is lost.
  Future<void> _applyModeVisibility() async {
    final controller = _controller;
    if (controller == null) return;
    await controller.setLayerVisibility(_sitesLayer, _mode == MapMode.threat);
    await controller.setLayerVisibility(_sitesPlainLayer, _mode == MapMode.conflict);
    await controller.setLayerVisibility(_pleiadesLayer, _showPleiades);
    await controller.setLayerVisibility(_densityLayer, _showDensity);
    await controller.setLayerVisibility(_models3dLayer, _showModels3d);
    await controller.setLayerVisibility(_radiusLayer, _showRadius);
    await controller.setLayerVisibility(_eventsLayer, _showEvents);
    for (final id in _buildingLayerIds) {
      await controller.setLayerVisibility(id, _showBuildings);
    }
  }

  /// Service/permission checks plus the current position, shared by the locate
  /// button and the routing flow. Returns null (after showing a message) when
  /// the location is unavailable.
  Future<Position?> _getPosition() async {
    if (!await Geolocator.isLocationServiceEnabled()) {
      _showLocationMessage('Location services are off. Enable them to locate.');
      return null;
    }
    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    if (permission == LocationPermission.denied ||
        permission == LocationPermission.deniedForever) {
      _showLocationMessage('Location permission denied.');
      return null;
    }
    return Geolocator.getCurrentPosition();
  }

  /// Foreground locate: request permission, get the current position, recentre
  /// the camera, show the location dot, and report the nearest scored site.
  Future<void> _locateMe() async {
    final controller = _controller;
    if (controller == null || _locating) return;
    setState(() => _locating = true);
    try {
      final position = await _getPosition();
      if (position == null || !mounted) return;
      setState(() => _myLocationEnabled = true);
      await controller.animateCamera(
        CameraUpdate.newLatLngZoom(
          LatLng(position.latitude, position.longitude),
          7.0,
        ),
      );
      final nearest = _findNearestSite(position.latitude, position.longitude);
      if (mounted) setState(() => _nearest = nearest);
    } catch (_) {
      _showLocationMessage('Could not get your location.');
    } finally {
      if (mounted) setState(() => _locating = false);
    }
  }

  /// Request an ORS route from the current position to a site and show it on
  /// the map. Location comes from the shared permission flow; the camera is
  /// fitted to the route and a summary panel appears (profile switch + clear).
  Future<void> _routeToSite(_RouteTarget target, RouteProfile profile) async {
    final controller = _controller;
    if (controller == null || _routingBusy) return;
    if (!RouteService.isConfigured) {
      _showLocationMessage(
        'Routing needs an OpenRouteService key: build the app with '
        '--dart-define=ORS_API_KEY=<key>.',
      );
      return;
    }
    setState(() => _routingBusy = true);
    try {
      final position = await _getPosition();
      if (position == null || !mounted) return;
      setState(() => _myLocationEnabled = true);
      final route = await RouteService.fetchRoute(
        from: LatLng(position.latitude, position.longitude),
        to: LatLng(target.lat, target.lon),
        profile: profile,
      );
      if (!mounted) return;
      setState(() {
        _route = route;
        _routeTarget = target;
        // The route replaces the nearest-site panel (same screen corner).
        _nearest = null;
      });
      await controller.setGeoJsonSource(_routeSource, route.toGeojson());
      await _fitCameraToRoute(route);
    } on RouteException catch (error) {
      _showLocationMessage(error.message);
    } catch (_) {
      _showLocationMessage('Routing failed.');
    } finally {
      if (mounted) setState(() => _routingBusy = false);
    }
  }

  /// Re-request the active route with the other profile (drive/walk).
  Future<void> _setRouteProfile(RouteProfile profile) async {
    final target = _routeTarget;
    if (target == null || _route?.profile == profile) return;
    await _routeToSite(target, profile);
  }

  /// Remove the route line and panel.
  Future<void> _clearRoute() async {
    setState(() {
      _route = null;
      _routeTarget = null;
    });
    await _controller?.setGeoJsonSource(_routeSource, _emptyGeojson);
  }

  Future<void> _fitCameraToRoute(RouteResult route) async {
    var minLat = route.points.first.latitude;
    var maxLat = minLat;
    var minLon = route.points.first.longitude;
    var maxLon = minLon;
    for (final p in route.points) {
      if (p.latitude < minLat) minLat = p.latitude;
      if (p.latitude > maxLat) maxLat = p.latitude;
      if (p.longitude < minLon) minLon = p.longitude;
      if (p.longitude > maxLon) maxLon = p.longitude;
    }
    await _controller?.animateCamera(
      CameraUpdate.newLatLngBounds(
        LatLngBounds(
          southwest: LatLng(minLat, minLon),
          northeast: LatLng(maxLat, maxLon),
        ),
        left: 48,
        right: 48,
        top: 140,
        bottom: 180,
      ),
    );
  }

  void _showLocationMessage(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message)));
  }

  /// Cheap proximity check: nearest scored site to a coordinate over the bundled
  /// sites (no backend; Geolocator's haversine distance).
  _NearestSite? _findNearestSite(double lat, double lon) {
    final features = (_sitesGeojson?['features'] as List?) ?? const [];
    _NearestSite? best;
    for (final feature in features) {
      final coords =
          ((feature as Map)['geometry']?['coordinates'] as List?) ?? const [];
      if (coords.length < 2) continue;
      final metres = Geolocator.distanceBetween(
        lat,
        lon,
        (coords[1] as num).toDouble(),
        (coords[0] as num).toDouble(),
      );
      if (best == null || metres < best.distanceMetres) {
        final props = (feature['properties'] as Map?) ?? const {};
        best = _NearestSite(
          name: (props['name'] ?? '').toString(),
          level: (props['threat_level'] ?? '').toString(),
          distanceMetres: metres,
          lat: (coords[1] as num).toDouble(),
          lon: (coords[0] as num).toDouble(),
        );
      }
    }
    return best;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: AppColors.sandstone,
        foregroundColor: AppColors.chromeOnColor,
        title: const Text('Heritage at Risk'),
        actions: [
          IconButton(
            tooltip: 'About this map',
            icon: const Icon(Icons.info_outline),
            onPressed: () => showModalBottomSheet<void>(
              context: context,
              showDragHandle: false,
              isScrollControlled: true,
              builder: (_) => const InfoSheet(),
            ),
          ),
          IconButton(
            tooltip: 'Sites by country',
            icon: const Icon(Icons.format_list_bulleted),
            onPressed: _openSiteList,
          ),
          IconButton(
            tooltip: widget.isDark ? 'Light theme' : 'Dark theme',
            icon: Icon(
              widget.isDark
                  ? Icons.light_mode_outlined
                  : Icons.dark_mode_outlined,
            ),
            onPressed: widget.onToggleTheme,
          ),
        ],
      ),
      body: Stack(
        children: [
          MapLibreMap(
            styleString: Basemap.forBrightnessDark(widget.isDark),
            initialCameraPosition: const CameraPosition(
              target: LatLng(34.0, 38.0),
              zoom: 3.6,
            ),
            onMapCreated: (controller) {
              _controller = controller;
              controller.onFeatureTapped.add(_onFeatureTapped);
            },
            onMapClick: _onMapClick,
            onStyleLoadedCallback: _onStyleLoaded,
            compassEnabled: true,
            myLocationEnabled: _myLocationEnabled,
          ),
          Positioned(
            top: 12,
            left: 12,
            right: 12,
            child: Column(
              children: [
                Row(
                  children: [
                    Expanded(child: _ModeSwitch(mode: _mode, onChanged: _setMode)),
                    const SizedBox(width: 8),
                    _PanelCollapseButton(
                      expanded: _topInfoExpanded,
                      onTap: () => setState(
                        () => _topInfoExpanded = !_topInfoExpanded,
                      ),
                    ),
                  ],
                ),
                if (_topInfoExpanded) ...[
                  const SizedBox(height: 8),
                  if (_mode == MapMode.threat)
                    _ContextPanel(
                      siteCount: _siteCount,
                      inDangerCount: _inDangerCount,
                    )
                  else
                    _ConflictInfoPanel(
                      eventCount: _totalConflictEvents,
                      siteCount: _conflictSiteCount,
                      onShowOverview: _showConflictOverview,
                    ),
                ],
              ],
            ),
          ),
          Positioned(
            left: 12,
            bottom: 24,
            child: ThreatLegend(
              conflictMode: _mode == MapMode.conflict,
              activeLevels: _activeLevels,
              showPleiades: _showPleiades,
              showDensity: _showDensity,
              showBuildings: _showBuildings,
              showModels3d: _showModels3d,
              showRadius: _showRadius,
              showEvents: _showEvents,
              onToggleLevel: _toggleLevel,
              onTogglePleiades: _togglePleiades,
              onToggleDensity: _toggleDensity,
              onToggleBuildings: _toggleBuildings,
              onToggleModels3d: _toggleModels3d,
              onToggleRadius: _toggleRadius,
              onToggleEvents: _toggleEvents,
            ),
          ),
          // Route summary and nearest-site panels share the corner above the
          // FAB; an active route takes precedence.
          if (_route != null && _routeTarget != null)
            Positioned(
              right: 12,
              bottom: 88,
              child: _RoutePanel(
                route: _route!,
                targetName: _routeTarget!.name,
                busy: _routingBusy,
                onProfileChanged: _setRouteProfile,
                onDismiss: _clearRoute,
              ),
            )
          else if (_nearest != null)
            Positioned(
              right: 12,
              bottom: 88,
              child: _NearestSitePanel(
                nearest: _nearest!,
                routing: _routingBusy,
                onRoute: () => _routeToSite(
                  _RouteTarget(
                    name: _nearest!.name,
                    lat: _nearest!.lat,
                    lon: _nearest!.lon,
                  ),
                  _route?.profile ?? RouteProfile.drive,
                ),
                onDismiss: () => setState(() => _nearest = null),
              ),
            ),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: _locating ? null : _locateMe,
        backgroundColor: AppColors.sandstone,
        foregroundColor: AppColors.chromeOnColor,
        tooltip: 'My location',
        child: _locating
            ? const SizedBox(
                width: 22,
                height: 22,
                child: CircularProgressIndicator(
                  strokeWidth: 2.4,
                  color: AppColors.chromeOnColor,
                ),
              )
            : const Icon(Icons.my_location),
      ),
    );
  }
}

/// Destination of a routing request (a scored site).
class _RouteTarget {
  const _RouteTarget({required this.name, required this.lat, required this.lon});

  final String name;
  final double lat;
  final double lon;
}

/// Result of the nearest-site proximity check.
class _NearestSite {
  const _NearestSite({
    required this.name,
    required this.level,
    required this.distanceMetres,
    required this.lat,
    required this.lon,
  });

  final String name;
  final String level;
  final double distanceMetres;
  final double lat;
  final double lon;
}

/// Compact panel reporting the nearest scored site to the user's location.
class _NearestSitePanel extends StatelessWidget {
  const _NearestSitePanel({
    required this.nearest,
    required this.routing,
    required this.onRoute,
    required this.onDismiss,
  });

  final _NearestSite nearest;
  final bool routing;
  final VoidCallback onRoute;
  final VoidCallback onDismiss;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final km = nearest.distanceMetres / 1000.0;
    final distance = km >= 10
        ? '${km.toStringAsFixed(0)} km'
        : '${km.toStringAsFixed(1)} km';
    return Card(
      elevation: 3,
      color: theme.colorScheme.surface.withValues(alpha: 0.94),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 230),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(12, 8, 6, 8),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Nearest site · $distance',
                      style: theme.textTheme.labelMedium?.copyWith(
                        color: theme.colorScheme.outline,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      nearest.name,
                      style: theme.textTheme.bodyMedium?.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    Text(
                      AppColors.threatLabel(nearest.level),
                      style: theme.textTheme.bodySmall,
                    ),
                    const SizedBox(height: 6),
                    // Routing entry point: directions to the nearest site.
                    ActionChip(
                      avatar: routing
                          ? const SizedBox(
                              width: 14,
                              height: 14,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Icon(Icons.directions_outlined, size: 16),
                      label: const Text('Route'),
                      visualDensity: VisualDensity.compact,
                      onPressed: routing ? null : onRoute,
                    ),
                  ],
                ),
              ),
              InkWell(
                onTap: onDismiss,
                borderRadius: BorderRadius.circular(16),
                child: const Padding(
                  padding: EdgeInsets.all(4),
                  child: Icon(Icons.close, size: 18),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Summary panel for the active route: destination, distance and duration for
/// the chosen profile, a drive/walk switch and a clear button.
class _RoutePanel extends StatelessWidget {
  const _RoutePanel({
    required this.route,
    required this.targetName,
    required this.busy,
    required this.onProfileChanged,
    required this.onDismiss,
  });

  final RouteResult route;
  final String targetName;
  final bool busy;
  final ValueChanged<RouteProfile> onProfileChanged;
  final VoidCallback onDismiss;

  String get _distance {
    final km = route.distanceMetres / 1000.0;
    return km >= 10 ? '${km.toStringAsFixed(0)} km' : '${km.toStringAsFixed(1)} km';
  }

  String get _duration {
    final minutes = (route.durationSeconds / 60).round();
    if (minutes < 60) return '$minutes min';
    return '${minutes ~/ 60} h ${minutes % 60} min';
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      elevation: 3,
      color: theme.colorScheme.surface.withValues(alpha: 0.94),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 250),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(12, 8, 6, 10),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Text(
                      'Route · $_distance · $_duration',
                      style: theme.textTheme.labelMedium?.copyWith(
                        color: theme.colorScheme.outline,
                      ),
                    ),
                  ),
                  InkWell(
                    onTap: onDismiss,
                    borderRadius: BorderRadius.circular(16),
                    child: const Padding(
                      padding: EdgeInsets.all(4),
                      child: Icon(Icons.close, size: 18),
                    ),
                  ),
                ],
              ),
              Text(
                targetName,
                style: theme.textTheme.bodyMedium?.copyWith(
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 6),
              SegmentedButton<RouteProfile>(
                segments: const [
                  ButtonSegment(
                    value: RouteProfile.drive,
                    icon: Icon(Icons.directions_car_outlined, size: 16),
                    label: Text('Drive'),
                  ),
                  ButtonSegment(
                    value: RouteProfile.walk,
                    icon: Icon(Icons.directions_walk_outlined, size: 16),
                    label: Text('Walk'),
                  ),
                ],
                selected: {route.profile},
                onSelectionChanged: busy
                    ? null
                    : (selection) => onProfileChanged(selection.first),
                showSelectedIcon: false,
                style: const ButtonStyle(visualDensity: VisualDensity.compact),
              ),
              const SizedBox(height: 4),
              Text(
                'Routing: openrouteservice.org',
                style: theme.textTheme.labelSmall?.copyWith(
                  color: theme.colorScheme.outline,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Context heading over the map (mirrors the prototype's title panel): a short
/// description of what the map shows, plus the site count.
class _ContextPanel extends StatelessWidget {
  const _ContextPanel({required this.siteCount, required this.inDangerCount});

  final int siteCount;
  final int inDangerCount;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      elevation: 3,
      color: theme.colorScheme.surface.withValues(alpha: 0.94),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(12, 10, 12, 10),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (siteCount > 0)
              Text(
                '$siteCount World Heritage Sites · $inDangerCount in danger',
                style: theme.textTheme.titleSmall?.copyWith(
                  fontWeight: FontWeight.w600,
                ),
              ),
            const SizedBox(height: 2),
            Text(
              'Weighted threat score per site. Tap ⓘ for sources and method.',
              style: theme.textTheme.bodySmall,
            ),
          ],
        ),
      ),
    );
  }
}

/// Segmented switch between the threat and conflict views (one shared map).
class _ModeSwitch extends StatelessWidget {
  const _ModeSwitch({required this.mode, required this.onChanged});

  final MapMode mode;
  final ValueChanged<MapMode> onChanged;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      elevation: 3,
      color: theme.colorScheme.surface.withValues(alpha: 0.94),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(4),
        child: SegmentedButton<MapMode>(
          segments: const [
            ButtonSegment(
              value: MapMode.threat,
              label: Text('Threat'),
              icon: Icon(Icons.shield_outlined, size: 18),
            ),
            ButtonSegment(
              value: MapMode.conflict,
              label: Text('Conflict'),
              icon: Icon(Icons.crisis_alert_outlined, size: 18),
            ),
          ],
          selected: {mode},
          onSelectionChanged: (selection) => onChanged(selection.first),
          showSelectedIcon: false,
          style: const ButtonStyle(visualDensity: VisualDensity.compact),
        ),
      ),
    );
  }
}

/// Compact one-line heading for the conflict view. The detail (what each layer
/// means, how they feed the score) lives in the legend and the info button, so
/// this panel stays small and leaves the map room.
class _ConflictInfoPanel extends StatelessWidget {
  const _ConflictInfoPanel({
    required this.eventCount,
    required this.siteCount,
    required this.onShowOverview,
  });

  final int eventCount;
  final int siteCount;
  final VoidCallback onShowOverview;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final tally = eventCount > 0
        ? '$eventCount conflict events (UCDP) near $siteCount sites, 30 km.'
        : 'Conflict events (UCDP), within 30 km of each site.';
    return Card(
      elevation: 3,
      color: theme.colorScheme.surface.withValues(alpha: 0.94),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: InkWell(
        onTap: onShowOverview,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(12, 8, 8, 8),
          child: Row(
            children: [
              Icon(
                Icons.crisis_alert_outlined,
                size: 16,
                color: theme.colorScheme.outline,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(tally, style: theme.textTheme.bodySmall),
              ),
              const SizedBox(width: 4),
              Icon(
                Icons.bar_chart_rounded,
                size: 18,
                color: theme.colorScheme.primary,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Small square card with a chevron that folds the top info panel away,
/// leaving only the mode switch. Mirrors the legend's collapse affordance.
class _PanelCollapseButton extends StatelessWidget {
  const _PanelCollapseButton({required this.expanded, required this.onTap});

  final bool expanded;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      elevation: 3,
      color: theme.colorScheme.surface.withValues(alpha: 0.94),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(8),
          child: Icon(
            expanded ? Icons.expand_less : Icons.expand_more,
            size: 20,
            color: theme.colorScheme.outline,
          ),
        ),
      ),
    );
  }
}
