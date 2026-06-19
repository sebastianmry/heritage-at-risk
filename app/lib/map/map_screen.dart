import 'dart:convert';
import 'dart:math' show Point;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show rootBundle;
import 'package:geolocator/geolocator.dart';
import 'package:maplibre_gl/maplibre_gl.dart';

import '../basemap.dart';
import '../theme.dart';
import 'info_sheet.dart';
import 'model_3d_sheet.dart';
import 'pleiades_sheet.dart';
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

  /// Only the conflict data: UCDP events, GKG strike coverage, the 30 km radius.
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
  static const String _eventsSource = 'ucdp-events';
  static const String _eventsLayer = 'ucdp-events-circles';
  static const String _strikesSource = 'gkg-strikes';
  static const String _strikesLayer = 'gkg-strikes-circles';

  MapLibreMapController? _controller;

  Map<String, dynamic>? _sitesGeojson;
  Map<String, dynamic>? _pleiadesGeojson;
  Map<String, dynamic>? _densityGeojson;
  Map<String, dynamic>? _models3dGeojson;
  Map<String, dynamic>? _radiusGeojson;
  Map<String, dynamic>? _eventsGeojson;
  Map<String, dynamic>? _strikesGeojson;

  MapMode _mode = MapMode.threat;

  final Set<String> _activeLevels = {'high', 'medium', 'low'};
  bool _showPleiades = true;
  bool _showDensity = true;
  bool _showBuildings = true;
  bool _showModels3d = true;
  bool _showRadius = false;
  bool _showEvents = false;
  bool _showStrikes = false;
  int _siteCount = 0;
  int _inDangerCount = 0;

  /// Foreground location: the device-location dot is shown once the user grants
  /// permission via the locate button. Off until then (no passive tracking).
  bool _myLocationEnabled = false;
  bool _locating = false;
  _NearestSite? _nearest;

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
    _eventsGeojson ??= await _loadGeojson('assets/data/ucdp_events.geojson');
    _strikesGeojson ??= await _loadGeojson('assets/data/gkg_strikes.geojson');
    final features = (_sitesGeojson!['features'] as List?) ?? const [];
    final count = features.length;
    final inDanger = features
        .where((f) => (f as Map)['properties']?['in_danger'] == true)
        .length;
    if (mounted && (count != _siteCount || inDanger != _inDangerCount)) {
      setState(() {
        _siteCount = count;
        _inDangerCount = inDanger;
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
        lineWidth: 1.2,
        lineOpacity: 0.55,
        lineDasharray: [2, 2],
      ),
    );

    // UCDP conflict events as small crimson dots (below the markers): the raw
    // georeferenced events that the conflict component counts per site (only the
    // ones within the 30 km site radius are exported, so layer == scored events).
    // One flat colour (violence type stays in the data but is not encoded here).
    // Dense, so off by default and non-interactive (taps belong to the sites).
    await controller.addGeoJsonSource(_eventsSource, _eventsGeojson!);
    await controller.addCircleLayer(
      _eventsSource,
      _eventsLayer,
      const CircleLayerProperties(
        circleColor: '#B2182B',
        circleRadius: [
          'interpolate',
          ['linear'],
          ['zoom'],
          4,
          1.8,
          9,
          3.5,
          13,
          5.5,
        ],
        circleOpacity: 0.55,
        circleStrokeColor: '#7F0E1E',
        circleStrokeWidth: 0.4,
      ),
      enableInteraction: false,
    );

    // GDELT-GKG strike coverage as deep-orange dots, aggregated per place and
    // sized by coverage-days (radius by 'days', one hit per place per day, media
    // megaphone removed). Distinct hue from the UCDP crimson: this is the noisier,
    // media-based signal of (also non-lethal) strikes that UCDP misses, blended
    // into the conflict component. Off by default, non-interactive (taps belong
    // to the sites).
    await controller.addGeoJsonSource(_strikesSource, _strikesGeojson!);
    await controller.addCircleLayer(
      _strikesSource,
      _strikesLayer,
      const CircleLayerProperties(
        circleColor: '#F4640A',
        circleRadius: [
          'interpolate',
          ['linear'],
          ['get', 'days'],
          1,
          2.0,
          60,
          6.0,
          360,
          12.0,
        ],
        circleOpacity: 0.5,
        circleStrokeColor: '#9C3D00',
        circleStrokeWidth: 0.4,
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
    await controller.setLayerVisibility(_strikesLayer, _showStrikes);
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

  Future<void> _showDetailAt(Point<double> point, String layerId) async {
    final controller = _controller;
    if (controller == null) return;
    // Small rectangle around the tap (tolerance instead of a single pixel) on
    // the given layer; coordinates are in device pixels.
    final rect = Rect.fromCenter(
      center: Offset(point.x, point.y),
      width: 30,
      height: 30,
    );
    final features = await controller.queryRenderedFeaturesInRect(rect, [
      layerId,
    ], null);
    if (features.isEmpty || !mounted) return;
    final properties = _extractProperties(features.first);
    if (properties == null) return;
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: false,
      builder: (_) {
        if (layerId == _pleiadesLayer) {
          return PleiadesSheet(properties: properties);
        }
        if (layerId == _models3dLayer) {
          return Model3DSheet(properties: properties);
        }
        return SiteDetailSheet(properties: properties);
      },
    );
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

  void _toggleStrikes(bool show) {
    setState(() => _showStrikes = show);
    _controller?.setLayerVisibility(_strikesLayer, show);
  }

  /// Switch between the threat and conflict views. Resets each view's layer set
  /// to its sensible default (the user can still toggle within a view), then
  /// applies the visibilities to the single shared map.
  void _setMode(MapMode mode) {
    if (mode == _mode) return;
    setState(() {
      _mode = mode;
      final conflict = mode == MapMode.conflict;
      // Conflict view: only the three conflict layers; heritage context off.
      _showRadius = conflict;
      _showEvents = conflict;
      _showStrikes = conflict;
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
    await controller.setLayerVisibility(_strikesLayer, _showStrikes);
    for (final id in _buildingLayerIds) {
      await controller.setLayerVisibility(id, _showBuildings);
    }
  }

  /// Foreground locate: request permission, get the current position, recentre
  /// the camera, show the location dot, and report the nearest scored site.
  Future<void> _locateMe() async {
    final controller = _controller;
    if (controller == null || _locating) return;
    setState(() => _locating = true);
    try {
      if (!await Geolocator.isLocationServiceEnabled()) {
        _showLocationMessage('Location services are off. Enable them to locate.');
        return;
      }
      var permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
      }
      if (permission == LocationPermission.denied ||
          permission == LocationPermission.deniedForever) {
        _showLocationMessage('Location permission denied.');
        return;
      }

      final position = await Geolocator.getCurrentPosition();
      if (!mounted) return;
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
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(builder: (_) => const SiteListScreen()),
            ),
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
                _ModeSwitch(mode: _mode, onChanged: _setMode),
                const SizedBox(height: 8),
                if (_mode == MapMode.threat)
                  _ContextPanel(
                    siteCount: _siteCount,
                    inDangerCount: _inDangerCount,
                  )
                else
                  const _ConflictInfoPanel(),
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
              showStrikes: _showStrikes,
              onToggleLevel: _toggleLevel,
              onTogglePleiades: _togglePleiades,
              onToggleDensity: _toggleDensity,
              onToggleBuildings: _toggleBuildings,
              onToggleModels3d: _toggleModels3d,
              onToggleRadius: _toggleRadius,
              onToggleEvents: _toggleEvents,
              onToggleStrikes: _toggleStrikes,
            ),
          ),
          if (_nearest != null)
            Positioned(
              right: 12,
              bottom: 88,
              child: _NearestSitePanel(
                nearest: _nearest!,
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

/// Result of the nearest-site proximity check.
class _NearestSite {
  const _NearestSite({
    required this.name,
    required this.level,
    required this.distanceMetres,
  });

  final String name;
  final String level;
  final double distanceMetres;
}

/// Compact panel reporting the nearest scored site to the user's location.
class _NearestSitePanel extends StatelessWidget {
  const _NearestSitePanel({required this.nearest, required this.onDismiss});

  final _NearestSite nearest;
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
              'Weighted threat score per site in the MENA region, from four '
              'sources: in-danger status, travel advisory, conflict, natural hazard.',
              style: theme.textTheme.bodySmall,
            ),
            const SizedBox(height: 4),
            Text(
              'Conflict data: UCDP GED (Uppsala) + GDELT GKG (strikes)',
              style: theme.textTheme.labelSmall?.copyWith(
                color: theme.colorScheme.outline,
              ),
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
  const _ConflictInfoPanel();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      elevation: 3,
      color: theme.colorScheme.surface.withValues(alpha: 0.94),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
        child: Row(
          children: [
            Icon(
              Icons.crisis_alert_outlined,
              size: 16,
              color: theme.colorScheme.outline,
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                'Conflict near sites: lethal events (UCDP) + strike coverage '
                '(GDELT), 30 km. Tap ⓘ for detail.',
                style: theme.textTheme.bodySmall,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
