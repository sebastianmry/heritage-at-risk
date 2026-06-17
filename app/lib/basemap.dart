/// Basemap styles of the prototype: monochrome CARTO vector maps without an API
/// key, MapLibre-native and offline-capable. Deliberately restrained so the
/// threat-coloured sites stand out (colour = data encoding).
class Basemap {
  Basemap._();

  static const String positron =
      'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json';
  static const String darkMatter =
      'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';

  static String forBrightnessDark(bool isDark) =>
      isDark ? darkMatter : positron;
}
