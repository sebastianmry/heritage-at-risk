import 'package:flutter/material.dart';

import '../theme.dart';

/// Threat classes as assigned by the pipeline in `threat_level`.
enum ThreatLevel {
  high('high', 'High (7-10)', AppColors.threatHigh),
  medium('medium', 'Medium (3-6)', AppColors.threatMedium),
  low('low', 'Low (0-3)', AppColors.threatLow);

  const ThreatLevel(this.key, this.label, this.color);

  final String key;
  final String label;
  final Color color;
}

/// Map legend with a class filter and context-layer toggles.
///
/// Pure presentation control; reports changes back via callbacks and holds no
/// state itself (that lives in [MapScreen]).
class ThreatLegend extends StatelessWidget {
  const ThreatLegend({
    super.key,
    required this.activeLevels,
    required this.showPleiades,
    required this.showDensity,
    required this.showBuildings,
    required this.showModels3d,
    required this.showRadius,
    required this.showEvents,
    required this.showStrikes,
    required this.onToggleLevel,
    required this.onTogglePleiades,
    required this.onToggleDensity,
    required this.onToggleBuildings,
    required this.onToggleModels3d,
    required this.onToggleRadius,
    required this.onToggleEvents,
    required this.onToggleStrikes,
  });

  final Set<String> activeLevels;
  final bool showPleiades;
  final bool showDensity;
  final bool showBuildings;
  final bool showModels3d;
  final bool showRadius;
  final bool showEvents;
  final bool showStrikes;
  final ValueChanged<ThreatLevel> onToggleLevel;
  final ValueChanged<bool> onTogglePleiades;
  final ValueChanged<bool> onToggleDensity;
  final ValueChanged<bool> onToggleBuildings;
  final ValueChanged<bool> onToggleModels3d;
  final ValueChanged<bool> onToggleRadius;
  final ValueChanged<bool> onToggleEvents;
  final ValueChanged<bool> onToggleStrikes;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      elevation: 3,
      color: theme.colorScheme.surface.withValues(alpha: 0.94),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(12, 10, 12, 10),
        // Scrollable so the legend never overflows when the available height
        // shrinks (e.g. landscape): the card stays compact when it fits and
        // scrolls otherwise instead of throwing a RenderFlex overflow.
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Threat level',
                style: theme.textTheme.labelMedium?.copyWith(
                  color: theme.colorScheme.outline,
                ),
              ),
              const SizedBox(height: 6),
              for (final level in ThreatLevel.values)
                _LegendToggle(
                  color: level.color,
                  label: level.label,
                  active: activeLevels.contains(level.key),
                  onTap: () => onToggleLevel(level),
                ),
              const SizedBox(height: 8),
              Divider(height: 1, color: theme.colorScheme.outlineVariant),
              const SizedBox(height: 8),
              Text(
                'Context',
                style: theme.textTheme.labelMedium?.copyWith(
                  color: theme.colorScheme.outline,
                ),
              ),
              const SizedBox(height: 6),
              _LegendToggle(
                color: AppColors.pleiades,
                label: 'Ancient places (Pleiades)',
                active: showPleiades,
                onTap: () => onTogglePleiades(!showPleiades),
              ),
              _LegendToggle(
                color: const Color(0xFFE9852F),
                label: 'Heritage & old town density',
                active: showDensity,
                onTap: () => onToggleDensity(!showDensity),
              ),
              _LegendToggle(
                color: AppColors.buildingWarmLight,
                label: 'Buildings (high zoom)',
                active: showBuildings,
                onTap: () => onToggleBuildings(!showBuildings),
              ),
              _LegendToggle(
                color: const Color(0xFF0FB5C9),
                label: '3D models',
                active: showModels3d,
                onTap: () => onToggleModels3d(!showModels3d),
              ),
              _LegendToggle(
                color: const Color(0xFFD85A30),
                label: 'Conflict radius (30 km)',
                active: showRadius,
                onTap: () => onToggleRadius(!showRadius),
              ),
              _LegendToggle(
                color: const Color(0xFFB2182B),
                label: 'Conflict events (UCDP)',
                active: showEvents,
                onTap: () => onToggleEvents(!showEvents),
              ),
              _LegendToggle(
                color: const Color(0xFFF4640A),
                label: 'Strike coverage (GDELT)',
                active: showStrikes,
                onTap: () => onToggleStrikes(!showStrikes),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _LegendToggle extends StatelessWidget {
  const _LegendToggle({
    required this.color,
    required this.label,
    required this.active,
    required this.onTap,
  });

  final Color color;
  final String label;
  final bool active;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(6),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 3),
        child: Row(
          children: [
            Container(
              width: 11,
              height: 11,
              decoration: BoxDecoration(
                color: active ? color : Colors.transparent,
                border: Border.all(color: color, width: 1.5),
                shape: BoxShape.circle,
              ),
            ),
            const SizedBox(width: 8),
            Text(
              label,
              style: theme.textTheme.bodySmall?.copyWith(
                color: active
                    ? theme.colorScheme.onSurface
                    : theme.colorScheme.outline,
                decoration: active ? null : TextDecoration.lineThrough,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
