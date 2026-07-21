import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Whether the app is in dark mode. Driven by the basemap dark/light toggle in
/// MapScreen — one switch flips both the map tiles and every surface built from
/// [AppTheme] (cards, sheets, dialogs), so the whole app reads as one state
/// instead of following the OS dark-mode setting.
final basemapDarkModeProvider = StateProvider<bool>((ref) => false);

/// Central colour and theme definitions (single source of truth for the UI).
///
/// Deliberately keeps two colour worlds apart (GEOSPATIAL_DESIGN_GUIDE,
/// "Distinct"):
///   * UI chrome in a CORINE Land Cover yellow (light-only design),
///   * data (threat) in the inverted traffic-light ramp.
/// Threat is never encoded by colour alone, but always additionally through a
/// label and a number (accessibility).
class AppColors {
  AppColors._();

  // Desert-sand chrome (#FAD5A5), used both as the app-bar / chrome surface
  // and as the single interactive accent (buttons, FAB, selected states) so
  // chrome and controls read as one colour.
  static const Color brand = Color(0xFFFAD5A5);
  static const Color accent = Color(0xFFFAD5A5);
  static const String brandHex = '#FAD5A5';

  /// Warm near-black foreground used on the yellow chrome (app bar, FAB).
  static const Color onChrome = Color(0xFF2B2A1F);

  // Inverted traffic-light ramp for the threat score; identical to the colours
  // in sites.geojson (config.THREAT_LEVEL_COLORS of the pipeline). High = red.
  static const Color threatHigh = Color(0xFFD7191C);
  static const Color threatMedium = Color(0xFFFDAE61);
  static const Color threatLow = Color(0xFF1A9641);

  // Pleiades context, deliberately outside the threat ramp (indigo).
  static const Color pleiades = Color(0xFF5B4FC4);

  // Sequential single-hue red ramp for the UCDP conflict events, keyed on the
  // event year so the layer reads "recent activity is hotter" (newer = more
  // intense). The rolling 12-month window spans exactly two calendar years,
  // hence two steps: previous year mid-red, current year dark red (ColorBrewer
  // Reds; colourblind-safe and distinct from the diverging threat ramp).
  // Exposed as Color (legend swatch) and Hex (MapLibre paint).
  static const Color eventYearPrevious = Color(0xFFFB6A4A);
  static const Color eventYearCurrent = Color(0xFFA50F15);
  static const String eventYearPreviousHex = '#FB6A4A';
  static const String eventYearCurrentHex = '#A50F15';
  static const String eventStrokeHex = '#7F0E1E';

  /// Plain site markers in the conflict view (the threat ramp is intentionally
  /// not used there). Dark olive-gold so the dots stay visible on the light
  /// basemap and read as part of the CORINE palette. Exposed as Color (legend
  /// swatch) and Hex (MapLibre paint).
  static const Color conflictSite = Color(0xFF6E5F1E);
  static const String conflictSiteHex = '#6E5F1E';

  /// Heritage / old-town density heatmap accent (violet-magenta). Deliberately
  /// outside every other layer's hue (threat red, brand yellow, Pleiades
  /// indigo, 3D cyan) so the density shading reads as its own signal.
  static const Color density = Color(0xFF8E24AA);

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

/// Light and dark themes of the app. The app bar/FAB chrome stays the
/// desert-sand brand colour in both (set explicitly, not derived from the
/// seed) so the "brand" reads the same regardless of mode; only the derived
/// surfaces — cards, sheets, dialogs — switch with [basemapDarkModeProvider].
class AppTheme {
  AppTheme._();

  static ThemeData light() => _themeFor(Brightness.light);

  static ThemeData dark() => _themeFor(Brightness.dark);

  static ThemeData _themeFor(Brightness brightness) {
    final scheme = ColorScheme.fromSeed(
      seedColor: AppColors.accent,
      brightness: brightness,
    );
    return ThemeData(
      useMaterial3: true,
      colorScheme: scheme,
      fontFamily: 'Roboto',
      appBarTheme: const AppBarTheme(
        backgroundColor: AppColors.brand,
        foregroundColor: AppColors.onChrome,
      ),
    );
  }
}
