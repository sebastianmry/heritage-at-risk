import 'package:flutter/material.dart';

import '../theme.dart';

/// One site's conflict tally for the overview list.
class ConflictSiteTally {
  const ConflictSiteTally({
    required this.name,
    required this.countryIso2,
    required this.events,
    required this.threatLevel,
  });

  final String name;
  final String countryIso2;
  final int events;
  final String threatLevel;
}

/// Bottom sheet that summarises the conflict component: the total number of
/// georeferenced UCDP events near heritage sites and the per-site breakdown,
/// sorted by event count. Read-only; the data comes from the scored sites.
class ConflictOverviewSheet extends StatelessWidget {
  const ConflictOverviewSheet({
    super.key,
    required this.totalEvents,
    required this.siteCount,
    required this.sites,
  });

  final int totalEvents;
  final int siteCount;
  final List<ConflictSiteTally> sites;

  static const Map<String, Color> _threatColors = {
    'high': AppColors.threatHigh,
    'medium': AppColors.threatMedium,
    'low': AppColors.threatLow,
  };

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final maxEvents = sites.isEmpty ? 1 : sites.first.events;
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 4, 20, 16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Conflict overview', style: theme.textTheme.titleLarge),
            const SizedBox(height: 4),
            Text(
              'Georeferenced UCDP conflict events within 30 km of each '
              'World Heritage site (rolling 12-month window).',
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.outline,
              ),
            ),
            const SizedBox(height: 14),
            Row(
              children: [
                _StatTile(value: '$totalEvents', label: 'events near sites'),
                const SizedBox(width: 12),
                _StatTile(value: '$siteCount', label: 'affected sites'),
                const SizedBox(width: 12),
                _StatTile(
                  value: sites.isEmpty ? '0' : '${sites.first.events}',
                  label: 'max per site',
                ),
              ],
            ),
            const SizedBox(height: 16),
            Text(
              'By site',
              style: theme.textTheme.labelMedium?.copyWith(
                color: theme.colorScheme.outline,
              ),
            ),
            const SizedBox(height: 6),
            Flexible(
              child: sites.isEmpty
                  ? Padding(
                      padding: const EdgeInsets.symmetric(vertical: 24),
                      child: Text(
                        'No conflict events within the site radii.',
                        style: theme.textTheme.bodyMedium,
                      ),
                    )
                  : ListView.separated(
                      shrinkWrap: true,
                      itemCount: sites.length,
                      separatorBuilder: (_, _) => const SizedBox(height: 2),
                      itemBuilder: (context, index) => _SiteRow(
                        rank: index + 1,
                        site: sites[index],
                        maxEvents: maxEvents,
                        color: _threatColors[sites[index].threatLevel] ??
                            theme.colorScheme.outline,
                      ),
                    ),
            ),
          ],
        ),
      ),
    );
  }
}

class _StatTile extends StatelessWidget {
  const _StatTile({required this.value, required this.label});

  final String value;
  final String label;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 10),
        decoration: BoxDecoration(
          color: theme.colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              value,
              style: theme.textTheme.headlineSmall?.copyWith(
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 2),
            Text(
              label,
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

class _SiteRow extends StatelessWidget {
  const _SiteRow({
    required this.rank,
    required this.site,
    required this.maxEvents,
    required this.color,
  });

  final int rank;
  final ConflictSiteTally site;
  final int maxEvents;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final fraction = maxEvents <= 0 ? 0.0 : site.events / maxEvents;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          SizedBox(
            width: 22,
            child: Text(
              '$rank',
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.outline,
              ),
            ),
          ),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  site.countryIso2.isEmpty
                      ? site.name
                      : '${site.name}  ·  ${site.countryIso2}',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: theme.textTheme.bodyMedium,
                ),
                const SizedBox(height: 4),
                ClipRRect(
                  borderRadius: BorderRadius.circular(3),
                  child: LinearProgressIndicator(
                    value: fraction.clamp(0.02, 1.0),
                    minHeight: 5,
                    backgroundColor:
                        theme.colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
                    valueColor: AlwaysStoppedAnimation<Color>(color),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 12),
          Text(
            '${site.events}',
            style: theme.textTheme.titleSmall?.copyWith(
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}
