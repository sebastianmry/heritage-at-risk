import 'package:flutter/material.dart';

/// Explains the map: what the threat score is built from, what the threat
/// levels mean, what each legend layer shows, and the data provenance. Opened
/// from the info button in the app bar so the on-map legend can stay compact
/// (short labels, the detail lives here).
class InfoSheet extends StatelessWidget {
  const InfoSheet({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return SafeArea(
      child: DraggableScrollableSheet(
        expand: false,
        initialChildSize: 0.7,
        maxChildSize: 0.95,
        minChildSize: 0.4,
        builder: (context, controller) => ListView(
          controller: controller,
          padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
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
            const SizedBox(height: 14),
            Text('About this map', style: theme.textTheme.titleLarge),
            const SizedBox(height: 16),

            _SectionTitle('Threat score'),
            Text(
              'Each World Heritage Site carries a 0–10 score from four weighted, '
              'independent sources:',
              style: theme.textTheme.bodyMedium,
            ),
            const SizedBox(height: 8),
            const _MetaRow('In-danger status', 'UNESCO World Heritage Centre', '×3'),
            const _MetaRow('Travel advisory', 'German Federal Foreign Office', '×3'),
            const _MetaRow('Conflict', 'UCDP GED, within 30 km', '×3'),
            const _MetaRow('Natural hazard', 'ThinkHazard! (World Bank), quake/flood', '×1'),
            const SizedBox(height: 12),

            _SectionTitle('Threat levels'),
            Text(
              'Low 0–3   ·   Medium 3–6   ·   High 6–10',
              style: theme.textTheme.bodyMedium,
            ),
            const SizedBox(height: 12),

            _SectionTitle('Map layers'),
            const _LayerRow(Color(0xFF5B4FC4), 'Ancient places',
                'Pleiades gazetteer of antiquity (context, no score)'),
            const _LayerRow(Color(0xFFE9852F), 'Heritage & old town density',
                'OpenStreetMap historic sites and buildings'),
            const _LayerRow(Color(0xFF7E6238), 'Buildings',
                'Provider basemap footprints, shown at high zoom'),
            const _LayerRow(Color(0xFF0FB5C9), '3D models',
                'Public laser scans / photogrammetry (CyArk, Sketchfab)'),
            const _LayerRow(Color(0xFFD85A30), 'Conflict radius',
                'The 30 km area scored around each site'),
            const _LayerRow(Color(0xFFB2182B), 'Conflict events',
                'UCDP GED: verified lethal events (≥1 death)'),
            const SizedBox(height: 12),

            _SectionTitle('Data & licence'),
            Text(
              'Conflict window: the most recent 12 months (rolling). Sources are '
              'used under their own licences; this is a derived artefact for an '
              'academic project (BHT Berlin). The score is indicative, not an '
              'official risk assessment.',
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

class _SectionTitle extends StatelessWidget {
  const _SectionTitle(this.text);

  final String text;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Text(
        text,
        style: theme.textTheme.labelLarge?.copyWith(
          color: theme.colorScheme.primary,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}

class _MetaRow extends StatelessWidget {
  const _MetaRow(this.title, this.source, this.weight);

  final String title;
  final String source;
  final String weight;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
                Text(
                  source,
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.outline,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 12),
          Text(
            weight,
            style: theme.textTheme.bodyMedium?.copyWith(
              fontWeight: FontWeight.w600,
              color: theme.colorScheme.primary,
            ),
          ),
        ],
      ),
    );
  }
}

class _LayerRow extends StatelessWidget {
  const _LayerRow(this.color, this.title, this.detail);

  final Color color;
  final String title;
  final String detail;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            margin: const EdgeInsets.only(top: 4),
            width: 12,
            height: 12,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
                Text(
                  detail,
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.outline,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
