/// Basemap style of the app: a restrained vector map so the threat-coloured
/// sites stand out (colour = data encoding).
///
/// Preferred is MapTiler `dataviz-light` / `dataviz-dark`, a muted style pair
/// made for data overlays. The key is injected at build time via
/// `--dart-define=MAPTILER_KEY=...` (never hard-coded or committed, mirroring
/// the OpenRouteService key). Without a key the app falls back to the keyless
/// CARTO Positron/Dark Matter basemaps, so it always renders.
class Basemap {
  Basemap._();

  static const String _maptilerKey = String.fromEnvironment('MAPTILER_KEY');

  static const String _cartoPositron =
      'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json';
  static const String _cartoDarkMatter =
      'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';

  /// True when a MapTiler key was provided at build time.
  static bool get hasMaptiler => _maptilerKey.isNotEmpty;

  /// The style URL to hand to MapLibre: MapTiler dataviz-light/dark when a key
  /// is configured, otherwise the matching keyless CARTO fallback.
  static String style({bool dark = false}) {
    if (hasMaptiler) {
      final variant = dark ? 'dataviz-dark' : 'dataviz-light';
      return 'https://api.maptiler.com/maps/$variant/style.json?key=$_maptilerKey';
    }
    return dark ? _cartoDarkMatter : _cartoPositron;
  }
}
