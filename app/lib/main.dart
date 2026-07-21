import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'map/map_screen.dart';
import 'theme.dart';

void main() {
  runApp(const ProviderScope(child: HeritageApp()));
}

/// Root of the app. Light/dark is driven by [basemapDarkModeProvider] (the
/// basemap toggle in MapScreen), not the OS setting, so map tiles and app
/// chrome always agree.
class HeritageApp extends ConsumerWidget {
  const HeritageApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final dark = ref.watch(basemapDarkModeProvider);
    return MaterialApp(
      title: 'Heritage at Risk',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light(),
      darkTheme: AppTheme.dark(),
      themeMode: dark ? ThemeMode.dark : ThemeMode.light,
      home: const MapScreen(),
    );
  }
}
