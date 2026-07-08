import 'package:flutter/material.dart';

import '../theme.dart';

/// Compact bottom sheet for a single tapped UCDP conflict event.
///
/// Shows the GED violence category and date plus the best fatality estimate.
/// The data comes from the conflict-events GeoJSON (deliberately slim:
/// date/year/violence_type/deaths).
class ConflictEventSheet extends StatelessWidget {
  const ConflictEventSheet({super.key, required this.properties});

  final Map<String, dynamic> properties;

  String _str(String key) => '${properties[key] ?? ''}'.trim();

  int _int(String key) {
    final value = properties[key];
    if (value is num) return value.toInt();
    return int.tryParse('${value ?? 0}') ?? 0;
  }

  /// Dot colour matches the map's year ramp (current year = dark red).
  Color _yearColor(int year) => year == DateTime.now().year
      ? AppColors.eventYearCurrent
      : AppColors.eventYearPrevious;

  /// GED category as a readable title ("state-based conflict" -> capitalised).
  String get _title {
    final type = _str('violence_type');
    if (type.isEmpty) return 'Conflict event';
    return type[0].toUpperCase() + type.substring(1);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final date = _str('date');
    final deaths = _int('deaths');
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
                  child: Text(_title, style: theme.textTheme.titleMedium),
                ),
              ],
            ),
            const SizedBox(height: 14),
            _Row(label: 'Date', value: date.isEmpty ? '—' : date),
            _Row(label: 'Fatalities (best estimate)', value: '$deaths'),
            const SizedBox(height: 14),
            Text(
              'Source: UCDP GED (Uppsala Conflict Data Program), CC BY 4.0',
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
