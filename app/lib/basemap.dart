/// Basemap style of the app: a light, restrained vector map so the
/// threat-coloured sites stand out (colour = data encoding).
///
/// Preferred is MapTiler `dataviz-light`, a muted style made for data
/// overlays. Its key is injected at build time via
/// `--dart-define=MAPTILER_KEY=...` (never hard-coded or committed, mirroring
/// the OpenRouteService key). Without a key the app falls back to the keyless
/// CARTO Positron light basemap, so it always renders.
class Basemap {
  Basemap._();

  static const String _maptilerKey = String.fromEnvironment('MAPTILER_KEY');

  static const String _cartoPositron =
      'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json';

  /// True when a MapTiler key was provided at build time.
  static bool get hasMaptiler => _maptilerKey.isNotEmpty;

  /// The style URL to hand to MapLibre: MapTiler dataviz-light when a key is
  /// configured, otherwise the keyless CARTO Positron fallback.
  static String style() => hasMaptiler
      ? 'https://api.maptiler.com/maps/dataviz-light/style.json?key=$_maptilerKey'
      : _cartoPositron;
}
