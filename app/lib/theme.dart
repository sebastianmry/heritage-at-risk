import 'package:flutter/material.dart';

/// Central colour and theme definitions (single source of truth for the UI).
///
/// Deliberately keeps two colour worlds apart (GEOSPATIAL_DESIGN_GUIDE,
/// "Distinct"):
///   * UI chrome in a warm sandstone (thematically fitting for archaeology),
///   * data (threat) in the inverted traffic-light ramp.
/// Threat is never encoded by colour alone, but always additionally through a
/// label and a number (accessibility).
class AppColors {
  AppColors._();

  // Sandstone chrome for the UI, with a warm gold accent. Deep enough to carry
  // light cream text (see [chromeOnColor]).
  static const Color sandstone = Color(0xFF7E6238);
  static const Color sandstoneDark = Color(0xFF5E4A2A);
  static const Color accent = Color(0xFFFFC400);

  /// Cream foreground used on the sandstone chrome (app bar, sheet headers).
  static const Color chromeOnColor = Color(0xFFF5ECD8);

  // Inverted traffic-light ramp for the threat score; identical to the colours
  // in sites.geojson (config.THREAT_LEVEL_COLORS of the pipeline). High = red.
  static const Color threatHigh = Color(0xFFD7191C);
  static const Color threatMedium = Color(0xFFFDAE61);
  static const Color threatLow = Color(0xFF1A9641);

  // Pleiades context, deliberately outside the threat ramp (indigo).
  static const Color pleiades = Color(0xFF5B4FC4);

  // Warm tint for the basemap buildings (ember logic per theme, from the map
  // prototype). Exposed as Color (legend swatch) and Hex (MapLibre paint).
  static const Color buildingWarmLight = Color(0xFFD9B878);
  static const Color buildingWarmDark = Color(0xFF6B5836);
  static const String buildingWarmLightHex = '#D9B878';
  static const String buildingWarmDarkHex = '#6B5836';

  /// Threat colour for a pipeline `threat_level` key.
  static Color forThreatLevel(String level) {
    switch (level) {
      case 'high':
        return threatHigh;
      case 'medium':
        return threatMedium;
      default:
        return threatLow;
    }
  }

  /// Short English label for a pipeline `threat_level` key. Used instead of the
  /// German `threat_label` field carried in the data.
  static String threatLabel(String level) {
    switch (level) {
      case 'high':
        return 'high';
      case 'medium':
        return 'medium';
      default:
        return 'low';
    }
  }
}

/// Light and dark theme of the app, both built on the sandstone seed.
class AppTheme {
  AppTheme._();

  static ThemeData light() => _build(Brightness.light);
  static ThemeData dark() => _build(Brightness.dark);

  static ThemeData _build(Brightness brightness) {
    final scheme = ColorScheme.fromSeed(
      seedColor: AppColors.sandstone,
      brightness: brightness,
    );
    return ThemeData(
      useMaterial3: true,
      colorScheme: scheme,
      fontFamily: 'Roboto',
    );
  }
}
