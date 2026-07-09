import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'map/map_screen.dart';
import 'theme.dart';

void main() {
  runApp(const ProviderScope(child: HeritageApp()));
}

/// Root of the app. The design is light-only (no dark mode), so a single
/// [AppTheme.light] drives the whole UI.
class HeritageApp extends StatelessWidget {
  const HeritageApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Heritage at Risk',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light(),
      home: const MapScreen(),
    );
  }
}
