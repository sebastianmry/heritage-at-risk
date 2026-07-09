import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../theme.dart';

/// Bottom sheet for a tapped 3D-model marker (context layer, no threat score).
///
/// Shows the site, the model source/author/licence and a button that opens the
/// public 3D model in the external browser (laser scan, photogrammetry or
/// reconstruction). For non-WHS icons (e.g. Old City of Mosul) it makes clear
/// the site is not part of the scored UNESCO set.
class Model3DSheet extends StatelessWidget {
  const Model3DSheet({super.key, required this.properties, this.onRoute});

  final Map<String, dynamic> properties;

  /// Called when the user asks for directions to this monument (intra-site
  /// routing). Null hides the button.
  final VoidCallback? onRoute;

  static const Color _accent = Color(0xFF0FB5C9);

  String _str(String key) => '${properties[key] ?? ''}'.trim();

  bool _bool(String key) {
    final value = properties[key];
    if (value is bool) return value;
    return '$value'.toLowerCase() == 'true';
  }

  Future<void> _open(BuildContext context, String url) async {
    final messenger = ScaffoldMessenger.of(context);
    final uri = Uri.tryParse(url);
    if (uri == null) return;
    final ok = await launchUrl(uri, mode: LaunchMode.externalApplication);
    if (!ok) {
      messenger.showSnackBar(
        const SnackBar(content: Text('Could not open the model link')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final name = _str('name');
    final isWhs = _bool('is_whs');
    final source = _str('source');
    final author = _str('author');
    final license = _str('license');
    final note = _str('note');
    final url = _str('model_url');

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
                  const Icon(
                    Icons.view_in_ar_outlined,
                    size: 18,
                    color: _accent,
                  ),
                  const SizedBox(width: 8),
                  Text(
                    '3D model',
                    style: theme.textTheme.labelMedium?.copyWith(
                      color: theme.colorScheme.outline,
                    ),
                  ),
                  const Spacer(),
                  _Badge(
                    label: isWhs ? 'UNESCO WHS' : 'Not scored',
                    color: isWhs
                        ? AppColors.accent
                        : theme.colorScheme.outline,
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                name.isEmpty ? '(unnamed)' : name,
                style: theme.textTheme.titleLarge,
              ),
              if (!isWhs) ...[
                const SizedBox(height: 6),
                Text(
                  'Destroyed heritage outside the UNESCO World Heritage list, '
                  'shown for context only (no threat score).',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.outline,
                  ),
                ),
              ],
              const SizedBox(height: 14),
              if (source.isNotEmpty) _MetaRow(label: 'Source', value: source),
              if (author.isNotEmpty) _MetaRow(label: 'Author', value: author),
              if (license.isNotEmpty)
                _MetaRow(label: 'Licence', value: license),
              if (note.isNotEmpty) ...[
                const SizedBox(height: 8),
                Text(note, style: theme.textTheme.bodyMedium),
              ],
              const SizedBox(height: 16),
              if (url.isNotEmpty)
                SizedBox(
                  width: double.infinity,
                  child: FilledButton.icon(
                    style: FilledButton.styleFrom(backgroundColor: _accent),
                    onPressed: () => _open(context, url),
                    icon: const Icon(Icons.open_in_new, size: 18),
                    label: const Text('View 3D model'),
                  ),
                ),
              if (onRoute != null) ...[
                const SizedBox(height: 8),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton.tonalIcon(
                    onPressed: onRoute,
                    icon: const Icon(Icons.directions_outlined, size: 18),
                    label: const Text('Route here'),
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

class _Badge extends StatelessWidget {
  const _Badge({required this.label, required this.color});

  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.14),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color, width: 0.8),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w600,
          color: color,
        ),
      ),
    );
  }
}

class _MetaRow extends StatelessWidget {
  const _MetaRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 72,
            child: Text(
              label,
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.outline,
              ),
            ),
          ),
          Expanded(child: Text(value, style: theme.textTheme.bodyMedium)),
        ],
      ),
    );
  }
}
