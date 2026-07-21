/// Basemap style of the app: a restrained vector map so the threat-coloured
/// sites stand out (colour = data encoding).
///
/// MapTiler `dataviz-light` / `dataviz-dark`, a muted style pair made for data
/// overlays. The key is injected at build time via
/// `--dart-define=MAPTILER_KEY=...` (never hard-coded or committed, mirroring
/// the OpenRouteService key); the app requires it, there is no keyless
/// fallback.
class Basemap {
  Basemap._();

  static const String _maptilerKey = String.fromEnvironment('MAPTILER_KEY');

  /// The style URL to hand to MapLibre: MapTiler dataviz-light or dataviz-dark.
  static String style({bool dark = false}) {
    final variant = dark ? 'dataviz-dark' : 'dataviz-light';
    return 'https://api.maptiler.com/maps/$variant/style.json?key=$_maptilerKey';
  }
}
