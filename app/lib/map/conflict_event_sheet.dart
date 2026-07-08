import 'package:flutter/material.dart';

import '../theme.dart';

/// Compact bottom sheet for a single tapped ACLED conflict event.
///
/// Shows the event type and date, plus the fatality count and whether civilians
/// were targeted. The data comes from the conflict-events GeoJSON (deliberately
/// slim: date/year/sub_event_type/deaths/civilian_targeting).
class ConflictEventSheet extends StatelessWidget {
  const ConflictEventSheet({super.key, required this.properties});

  final Map<String, dynamic> properties;

  String _str(String key) => '${properties[key] ?? ''}'.trim();

  int _int(String key) {
    final value = properties[key];
    if (value is num) return value.toInt();
    return int.tryParse('${value ?? 0}') ?? 0;
  }

  bool _bool(String key) {
    final value = properties[key];
    if (value is bool) return value;
    return '$value'.toLowerCase() == 'true';
  }

  /// Dot colour matches the map's year ramp (newer = more intense red).
  Color _yearColor(int year) {
    switch (year) {
      case 2023:
        return AppColors.eventYear2023;
      case 2024:
        return AppColors.eventYear2024;
      case 2025:
        return AppColors.eventYear2025;
      default:
        return AppColors.eventYear2024;
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final type = _str('sub_event_type').isEmpty
        ? 'Conflict event'
        : _str('sub_event_type');
    final date = _str('date');
    final deaths = _int('deaths');
    final civilians = _bool('civilian_targeting');
    final dotColor = _yearColor(_int('year'));

    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 12, 20, 20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Container(
                width: 36,
                height: 4,
                decoration: BoxDecoration(
                  color: theme.colorScheme.outlineVariant,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const SizedBox(height: 16),
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  margin: const EdgeInsets.only(top: 5),
                  width: 12,
                  height: 12,
                  decoration: BoxDecoration(
                    color: dotColor,
                    shape: BoxShape.circle,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(type, style: theme.textTheme.titleMedium),
                ),
              ],
            ),
            const SizedBox(height: 14),
            _Row(label: 'Date', value: date.isEmpty ? '—' : date),
            _Row(label: 'Fatalities', value: '$deaths'),
            _Row(
              label: 'Civilian targeting',
              value: civilians ? 'Yes' : 'No',
            ),
            const SizedBox(height: 14),
            Text(
              'Source: ACLED (Armed Conflict Location & Event Data)',
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.outline,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Row extends StatelessWidget {
  const _Row({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        children: [
          Expanded(child: Text(label, style: theme.textTheme.bodyMedium)),
          Text(
            value,
            style: theme.textTheme.bodyMedium?.copyWith(
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}
