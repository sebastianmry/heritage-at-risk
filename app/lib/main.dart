import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'map/map_screen.dart';
import 'theme.dart';

void main() {
  runApp(const ProviderScope(child: HeritageApp()));
}

/// Root of the app. Holds the light/dark state that drives both the UI theme
/// and the basemap (shared toggle, see the map prototype).
class HeritageApp extends StatefulWidget {
  const HeritageApp({super.key});

  @override
  State<HeritageApp> createState() => _HeritageAppState();
}

class _HeritageAppState extends State<HeritageApp> {
  late bool _isDark = WidgetsBinding
          .instance.platformDispatcher.platformBrightness ==
      Brightness.dark;

  void _toggleTheme() => setState(() => _isDark = !_isDark);

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Heritage at Risk',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light(),
      darkTheme: AppTheme.dark(),
      themeMode: _isDark ? ThemeMode.dark : ThemeMode.light,
      home: MapScreen(isDark: _isDark, onToggleTheme: _toggleTheme),
    );
  }
}
