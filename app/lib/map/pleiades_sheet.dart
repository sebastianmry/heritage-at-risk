import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../theme.dart';

/// Bottom sheet for a tapped Pleiades place (ancient-world context layer).
///
/// Pleiades places carry no threat score; this sheet shows the name, the place
/// type and the source URL. The URL can be copied (no in-app browser, to keep
/// the app dependency-free).
class PleiadesSheet extends StatelessWidget {
  const PleiadesSheet({super.key, required this.properties, this.onRoute});

  final Map<String, dynamic> properties;

  /// Called when the user asks for walking/driving directions to this place
  /// (intra-site routing to individual monuments). Null hides the button.
  final VoidCallback? onRoute;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final name = '${properties['title'] ?? ''}'.trim();
    final type = '${properties['types'] ?? ''}'.replaceAll('_', ' ').trim();
    final url = '${properties['url'] ?? ''}'.trim();

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
                children: [
                  Container(
                    width: 12,
                    height: 12,
                    decoration: const BoxDecoration(
                      color: AppColors.pleiades,
                      shape: BoxShape.circle,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    'Ancient place (Pleiades)',
                    style: theme.textTheme.labelMedium?.copyWith(
                      color: theme.colorScheme.outline,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                name.isEmpty ? '(unnamed)' : name,
                style: theme.textTheme.titleLarge,
              ),
              if (type.isNotEmpty) ...[
                const SizedBox(height: 4),
                Text(type, style: theme.textTheme.bodySmall),
              ],
              const SizedBox(height: 14),
              Text(
                'Context layer, no threat score.',
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.colorScheme.outline,
                ),
              ),
              if (onRoute != null) ...[
                const SizedBox(height: 12),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton.tonalIcon(
                    onPressed: onRoute,
                    icon: const Icon(Icons.directions_outlined, size: 18),
                    label: const Text('Route here'),
                  ),
                ),
              ],
              if (url.isNotEmpty) ...[
                const SizedBox(height: 14),
                Divider(color: theme.colorScheme.outlineVariant, height: 1),
                const SizedBox(height: 10),
                InkWell(
                  borderRadius: BorderRadius.circular(6),
                  onTap: () {
                    Clipboard.setData(ClipboardData(text: url));
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('Pleiades URL copied')),
                    );
                  },
                  child: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 4),
                    child: Row(
                      children: [
                        Icon(
                          Icons.link,
                          size: 16,
                          color: theme.colorScheme.outline,
                        ),
                        const SizedBox(width: 6),
                        Expanded(
                          child: Text(
                            url.replaceFirst('https://', ''),
                            style: theme.textTheme.bodySmall?.copyWith(
                              color: AppColors.pleiades,
                            ),
                          ),
                        ),
                        Icon(
                          Icons.copy,
                          size: 14,
                          color: theme.colorScheme.outline,
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
