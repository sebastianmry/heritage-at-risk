import 'package:flutter/material.dart';

import '../theme.dart';

/// Bottom sheet with the threat breakdown of a tapped UNESCO site.
///
/// Shows the total score and the four weighted components (in-danger, travel
/// advisory, conflict, natural hazard) with raw value and contribution. Threat
/// is encoded redundantly through colour, label and number (accessibility).
class SiteDetailSheet extends StatelessWidget {
  const SiteDetailSheet({super.key, required this.properties});

  final Map<String, dynamic> properties;

  /// Short labels for ThinkHazard! hazard levels (VLO/LOW/MED/HIG/NDA).
  static const Map<String, String> _hazardLevels = {
    'VLO': 'V.low',
    'LOW': 'Low',
    'MED': 'Med',
    'HIG': 'High',
    'NDA': '—',
  };

  num _num(String key) {
    final value = properties[key];
    if (value is num) return value;
    return num.tryParse('${value ?? 0}') ?? 0;
  }

  bool _bool(String key) {
    final value = properties[key];
    if (value is bool) return value;
    return '$value'.toLowerCase() == 'true';
  }

  String _hazard(String key) =>
      _hazardLevels['${properties[key]}'.toUpperCase()] ?? '—';

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final level = '${properties['threat_level'] ?? 'low'}';
    final label = AppColors.threatLabel(level);
    final threatColor = AppColors.forThreatLevel(level);
    final totalScore = _num('total_score').toDouble();

    return SafeArea(
      child: SingleChildScrollView(
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
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '${properties['name'] ?? 'Unknown site'}',
                          style: theme.textTheme.titleLarge,
                        ),
                        const SizedBox(height: 4),
                        Row(
                          children: [
                            Icon(
                              Icons.place_outlined,
                              size: 15,
                              color: theme.colorScheme.outline,
                            ),
                            const SizedBox(width: 4),
                            Text(
                              '${properties['country_iso2'] ?? ''} · '
                              '${properties['category'] ?? ''} · UNESCO',
                              style: theme.textTheme.bodySmall,
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                  _ScoreBadge(
                    score: totalScore,
                    label: label,
                    color: threatColor,
                  ),
                ],
              ),
              const SizedBox(height: 18),
              _ComponentRow(
                color: AppColors.pleiades,
                title: 'UNESCO in-danger',
                value: _bool('in_danger') ? 'Yes' : 'No',
                contribution: _num('score_in_danger').toDouble(),
              ),
              _ComponentRow(
                color: const Color(0xFF378ADD),
                title: 'Travel advisory (AA)',
                value: 'Level ${_num('warning_level').toInt()}',
                contribution: _num('score_travel').toDouble(),
              ),
              _ComponentRow(
                color: const Color(0xFFD85A30),
                title: 'Conflicts 30 km (UCDP GED)',
                value: '${_num('conflict_count').toInt()} events',
                contribution: _num('score_conflict').toDouble(),
              ),
              _ComponentRow(
                color: const Color(0xFF7E57C2),
                title: 'Natural hazard (quake/flood)',
                value: 'EQ ${_hazard('eq_level')} · FL ${_hazard('fl_level')}',
                contribution: _num('score_natural').toDouble(),
              ),
              const SizedBox(height: 14),
              Divider(color: theme.colorScheme.outlineVariant, height: 1),
              const SizedBox(height: 10),
              Text(
                'Sources: UNESCO WHC · German Federal Foreign Office · UCDP GED (Uppsala) · ThinkHazard! (World Bank)',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.outline,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ScoreBadge extends StatelessWidget {
  const _ScoreBadge({
    required this.score,
    required this.label,
    required this.color,
  });

  final double score;
  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.14),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color, width: 0.8),
      ),
      child: Column(
        children: [
          Text(
            score.toStringAsFixed(1),
            style: TextStyle(
              fontSize: 22,
              fontWeight: FontWeight.w600,
              color: color,
            ),
          ),
          Text('/ 10 · $label', style: TextStyle(fontSize: 10, color: color)),
        ],
      ),
    );
  }
}

class _ComponentRow extends StatelessWidget {
  const _ComponentRow({
    required this.color,
    required this.title,
    required this.value,
    required this.contribution,
  });

  final Color color;
  final String title;
  final String value;
  final double contribution;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isActive = contribution > 0;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        children: [
          Container(
            width: 10,
            height: 10,
            decoration: BoxDecoration(
              color: color,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const SizedBox(width: 10),
          Expanded(child: Text(title, style: theme.textTheme.bodyMedium)),
          Text(
            value,
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.outline,
            ),
          ),
          const SizedBox(width: 12),
          SizedBox(
            width: 40,
            child: Text(
              isActive
                  ? '+${contribution.toStringAsFixed(1)}'
                  : contribution.toStringAsFixed(1),
              textAlign: TextAlign.right,
              style: theme.textTheme.bodyMedium?.copyWith(
                fontWeight: FontWeight.w600,
                color: isActive ? color : theme.colorScheme.outline,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
