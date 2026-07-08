import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show rootBundle;

/// Sortable, country-filterable list of every scored site.
///
/// A text companion to the map: reads the same `sites.geojson` artefact and
/// shows each site with its total threat score and level, grouped or filtered by
/// country. The score is always given as a number and a level word, never by
/// colour alone (accessibility, see the design guide).
class SiteListScreen extends StatefulWidget {
  const SiteListScreen({super.key});

  @override
  State<SiteListScreen> createState() => _SiteListScreenState();
}

class _SiteListScreenState extends State<SiteListScreen> {
  /// ISO-3166 alpha-2 to display name for the countries in scope.
  static const Map<String, String> _countryNames = {
    'IR': 'Iran', 'IL': 'Israel', 'SA': 'Saudi Arabia', 'EG': 'Egypt',
    'JO': 'Jordan', 'SY': 'Syria', 'IQ': 'Iraq', 'LB': 'Lebanon',
    'PS': 'Palestine', 'YE': 'Yemen', 'OM': 'Oman', 'BH': 'Bahrain',
    'AE': 'United Arab Emirates', 'QA': 'Qatar', 'KW': 'Kuwait',
  };

  List<_Site> _sites = const [];
  String _selectedIso2 = _allCountries;
  static const String _allCountries = '*';

  @override
  void initState() {
    super.initState();
    _loadSites();
  }

  Future<void> _loadSites() async {
    final raw = await rootBundle.loadString('assets/data/sites.geojson');
    final features = (jsonDecode(raw) as Map<String, dynamic>)['features'] as List;
    final sites = features
        .map((f) => _Site.fromFeature(f as Map))
        .toList()
      ..sort((a, b) => b.totalScore.compareTo(a.totalScore));
    setState(() => _sites = sites);
  }

  String _countryName(String iso2) => _countryNames[iso2] ?? iso2;

  /// Countries present in the data, ordered by their highest site score.
  List<String> get _countriesByPeak {
    final peak = <String, double>{};
    for (final site in _sites) {
      peak.update(site.iso2, (current) => current < site.totalScore ? site.totalScore : current,
          ifAbsent: () => site.totalScore);
    }
    final codes = peak.keys.toList()
      ..sort((a, b) => peak[b]!.compareTo(peak[a]!));
    return codes;
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final visible = _selectedIso2 == _allCountries
        ? _sites
        : _sites.where((s) => s.iso2 == _selectedIso2).toList();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Sites by country'),
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(54),
          child: _CountryFilterBar(
            countries: _countriesByPeak,
            countryName: _countryName,
            selected: _selectedIso2,
            allValue: _allCountries,
            onSelect: (iso2) => setState(() => _selectedIso2 = iso2),
          ),
        ),
      ),
      body: _sites.isEmpty
          ? const Center(child: CircularProgressIndicator())
          : ListView.separated(
              padding: const EdgeInsets.symmetric(vertical: 4),
              itemCount: visible.length,
              separatorBuilder: (_, _) =>
                  Divider(height: 1, color: theme.colorScheme.outlineVariant),
              itemBuilder: (context, index) {
                final site = visible[index];
                return _SiteTile(
                  site: site,
                  countryName: _countryName(site.iso2),
                  // Tapping a row returns to the map and recentres on the site.
                  onTap: () => Navigator.of(context).pop(
                    (lat: site.lat, lon: site.lon),
                  ),
                );
              },
            ),
    );
  }
}

/// Horizontally scrolling country filter, including an "All" entry.
class _CountryFilterBar extends StatelessWidget {
  const _CountryFilterBar({
    required this.countries,
    required this.countryName,
    required this.selected,
    required this.allValue,
    required this.onSelect,
  });

  final List<String> countries;
  final String Function(String) countryName;
  final String selected;
  final String allValue;
  final ValueChanged<String> onSelect;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 54,
      child: ListView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 9),
        children: [
          _FilterChip(
            label: 'All',
            selected: selected == allValue,
            onTap: () => onSelect(allValue),
          ),
          for (final iso2 in countries)
            _FilterChip(
              label: countryName(iso2),
              selected: selected == iso2,
              onTap: () => onSelect(iso2),
            ),
        ],
      ),
    );
  }
}

class _FilterChip extends StatelessWidget {
  const _FilterChip({required this.label, required this.selected, required this.onTap});

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: ChoiceChip(
        label: Text(label),
        selected: selected,
        onSelected: (_) => onTap(),
      ),
    );
  }
}

/// One site row: colour accent plus the level word and numeric score.
class _SiteTile extends StatelessWidget {
  const _SiteTile({
    required this.site,
    required this.countryName,
    required this.onTap,
  });

  final _Site site;
  final String countryName;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return ListTile(
      onTap: onTap,
      leading: Container(
        width: 12,
        height: 12,
        margin: const EdgeInsets.only(top: 6),
        decoration: BoxDecoration(color: site.color, shape: BoxShape.circle),
      ),
      title: Text(site.name, style: theme.textTheme.titleSmall),
      subtitle: Text(
        '$countryName · ${site.category} · ${site.level}',
        style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.outline),
      ),
      trailing: Text(
        site.totalScore.toStringAsFixed(1),
        style: theme.textTheme.titleMedium?.copyWith(
          fontWeight: FontWeight.w600,
          color: site.color,
        ),
      ),
    );
  }
}

/// Lightweight view model parsed from a site GeoJSON feature's properties.
class _Site {
  const _Site({
    required this.name,
    required this.iso2,
    required this.category,
    required this.level,
    required this.totalScore,
    required this.color,
    required this.lat,
    required this.lon,
  });

  final String name;
  final String iso2;
  final String category;
  final String level;
  final double totalScore;
  final Color color;
  final double lat;
  final double lon;

  factory _Site.fromFeature(Map feature) {
    final properties = (feature['properties'] as Map?) ?? const {};
    final coords = (feature['geometry'] as Map?)?['coordinates'] as List?;
    return _Site(
      name: (properties['name'] as String?) ?? 'Unknown',
      iso2: (properties['country_iso2'] as String?) ?? '',
      category: (properties['category'] as String?) ?? '',
      level: (properties['threat_level'] as String?) ?? '',
      totalScore: (properties['total_score'] as num?)?.toDouble() ?? 0,
      color: _parseHexColor(properties['threat_color'] as String?),
      lon: coords != null && coords.length >= 2 ? (coords[0] as num).toDouble() : 0,
      lat: coords != null && coords.length >= 2 ? (coords[1] as num).toDouble() : 0,
    );
  }
}

/// Parses a `#rrggbb` string to an opaque [Color]; falls back to grey.
Color _parseHexColor(String? hex) {
  if (hex == null || hex.length < 7) return const Color(0xFF9E9E9E);
  return Color(0xFF000000 | int.parse(hex.substring(1), radix: 16));
}
