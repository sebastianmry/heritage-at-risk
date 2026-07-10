import 'package:flutter/material.dart';

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

  // CORINE Land Cover inspired yellow chrome. `brand` is the pale arable-land
  // yellow (CLC 211, #FFFFA8), used as the app-bar / chrome surface with dark
  // text. `accent` is a deeper CORINE gold for the interactive primary
  // (buttons, FAB, selected states) so controls stay legible on the light UI.
  static const Color brand = Color(0xFFFFFFA8);
  static const Color accent = Color(0xFFCBA200);
  static const String brandHex = '#FFFFA8';

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

/// Light theme of the app. The design is deliberately light-only (no dark
/// mode): a CORINE gold seed drives the Material colour scheme, with a pale
/// CORINE-yellow app bar carrying dark chrome text.
class AppTheme {
  AppTheme._();

  static ThemeData light() {
    final scheme = ColorScheme.fromSeed(
      seedColor: AppColors.accent,
      brightness: Brightness.light,
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
