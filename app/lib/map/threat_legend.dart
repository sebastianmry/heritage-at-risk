import 'package:flutter/material.dart';

import '../theme.dart';

/// Threat classes as assigned by the pipeline in `threat_level`.
enum ThreatLevel {
  high('high', 'High', AppColors.threatHigh),
  medium('medium', 'Medium', AppColors.threatMedium),
  low('low', 'Low', AppColors.threatLow);

  const ThreatLevel(this.key, this.label, this.color);

  final String key;
  final String label;
  final Color color;
}

/// Map legend with a class filter and context-layer toggles.
///
/// Reports layer changes back via callbacks; the only state it owns is whether
/// the panel is expanded or collapsed to a compact header (so it can be folded
/// away to free up the map). The actual layer state lives in [MapScreen].
class ThreatLegend extends StatefulWidget {
  const ThreatLegend({
    super.key,
    required this.conflictMode,
    required this.activeLevels,
    required this.showPleiades,
    required this.showDensity,
    required this.showBuildings,
    required this.showModels3d,
    required this.showRadius,
    required this.showEvents,
    required this.onToggleLevel,
    required this.onTogglePleiades,
    required this.onToggleDensity,
    required this.onToggleBuildings,
    required this.onToggleModels3d,
    required this.onToggleRadius,
    required this.onToggleEvents,
  });

  final bool conflictMode;
  final Set<String> activeLevels;
  final bool showPleiades;
  final bool showDensity;
  final bool showBuildings;
  final bool showModels3d;
  final bool showRadius;
  final bool showEvents;
  final ValueChanged<ThreatLevel> onToggleLevel;
  final ValueChanged<bool> onTogglePleiades;
  final ValueChanged<bool> onToggleDensity;
  final ValueChanged<bool> onToggleBuildings;
  final ValueChanged<bool> onToggleModels3d;
  final ValueChanged<bool> onToggleRadius;
  final ValueChanged<bool> onToggleEvents;

  @override
  State<ThreatLegend> createState() => _ThreatLegendState();
}

class _ThreatLegendState extends State<ThreatLegend> {
  bool _expanded = true;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      elevation: 3,
      color: theme.colorScheme.surface.withValues(alpha: 0.94),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: EdgeInsets.fromLTRB(12, 8, 12, _expanded ? 10 : 8),
        // Scrollable so the legend never overflows when the available height
        // shrinks (e.g. landscape): the card stays compact when it fits and
        // scrolls otherwise instead of throwing a RenderFlex overflow.
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _LegendHeader(
                expanded: _expanded,
                onTap: () => setState(() => _expanded = !_expanded),
              ),
              if (_expanded) ...[
                const SizedBox(height: 8),
                _LegendBody(widget),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

/// Tappable title row that folds the legend open or shut.
class _LegendHeader extends StatelessWidget {
  const _LegendHeader({required this.expanded, required this.onTap});

  final bool expanded;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(6),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            'Legend',
            style: theme.textTheme.labelLarge?.copyWith(
              color: theme.colorScheme.onSurface,
            ),
          ),
          const SizedBox(width: 6),
          Icon(
            expanded ? Icons.expand_more : Icons.chevron_right,
            size: 18,
            color: theme.colorScheme.outline,
          ),
        ],
      ),
    );
  }
}

/// The full set of toggles, shown only while the legend is expanded.
class _LegendBody extends StatelessWidget {
  const _LegendBody(this.legend);

  final ThreatLegend legend;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final conflictMode = legend.conflictMode;
    final activeLevels = legend.activeLevels;
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
              // Threat view: the full legend (class filter + context layers).
              // Conflict view: only the three conflict layers (the explanatory
              // panel at the top already describes what they mean).
              if (!conflictMode) ...[
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
                    onTap: () => legend.onToggleLevel(level),
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
                  label: 'Ancient places',
                  active: legend.showPleiades,
                  onTap: () => legend.onTogglePleiades(!legend.showPleiades),
                ),
                _LegendToggle(
                  color: const Color(0xFFE9852F),
                  label: 'Heritage density',
                  active: legend.showDensity,
                  onTap: () => legend.onToggleDensity(!legend.showDensity),
                ),
                _LegendToggle(
                  color: AppColors.buildingWarmLight,
                  label: 'Buildings',
                  active: legend.showBuildings,
                  onTap: () => legend.onToggleBuildings(!legend.showBuildings),
                ),
                _LegendToggle(
                  color: const Color(0xFF0FB5C9),
                  label: '3D models',
                  active: legend.showModels3d,
                  onTap: () => legend.onToggleModels3d(!legend.showModels3d),
                ),
              ] else ...[
                Text(
                  'Conflict layers',
                  style: theme.textTheme.labelMedium?.copyWith(
                    color: theme.colorScheme.outline,
                  ),
                ),
                const SizedBox(height: 6),
                const _LegendStatic(
                  color: Color(0xFF7E6238),
                  label: 'Heritage sites',
                ),
                _LegendToggle(
                  color: const Color(0xFFD85A30),
                  label: 'Conflict radius',
                  active: legend.showRadius,
                  onTap: () => legend.onToggleRadius(!legend.showRadius),
                ),
                _LegendToggle(
                  color: const Color(0xFFD7191C),
                  label: 'Conflict events',
                  active: legend.showEvents,
                  onTap: () => legend.onToggleEvents(!legend.showEvents),
                ),
              ],
            ],
    );
  }
}

/// Non-interactive legend entry (a layer that is always shown, e.g. the
/// heritage sites in the conflict view).
class _LegendStatic extends StatelessWidget {
  const _LegendStatic({required this.color, required this.label});

  final Color color;
  final String label;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        children: [
          Container(
            width: 11,
            height: 11,
            decoration: BoxDecoration(
              color: color,
              border: Border.all(color: Colors.white, width: 1.2),
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 8),
          Text(
            label,
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurface,
            ),
          ),
        ],
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
                // Active dots get the same white ring as the map markers (and the
                // conflict-view legend); inactive stay hollow with a coloured ring.
                border: Border.all(
                  color: active ? Colors.white : color,
                  width: active ? 1.2 : 1.5,
                ),
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
