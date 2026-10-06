import 'package:flutter/material.dart';

import '../models/txn.dart';
import '../theme.dart';
import '../util/categories.dart';
import '../util/format.dart';

/// Seletor de mês em formato de pílula.
class MonthSwitcher extends StatelessWidget {
  const MonthSwitcher({super.key, required this.month, required this.onChanged});

  final DateTime month;
  final ValueChanged<DateTime> onChanged;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Container(
      height: 40,
      decoration: BoxDecoration(
        color: c.card,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: c.line),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          _arrow(context, Icons.chevron_left, -1, 'Mês anterior'),
          ConstrainedBox(
            constraints: const BoxConstraints(minWidth: 116),
            child: Text(
              monthLabel(month),
              textAlign: TextAlign.center,
              style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14, color: c.ink),
            ),
          ),
          _arrow(context, Icons.chevron_right, 1, 'Próximo mês'),
        ],
      ),
    );
  }

  Widget _arrow(BuildContext context, IconData icon, int delta, String tooltip) => IconButton(
    visualDensity: VisualDensity.compact,
    tooltip: tooltip,
    icon: Icon(icon, size: 20, color: context.colors.ink2),
    onPressed: () => onChanged(DateTime(month.year, month.month + delta)),
  );
}

/// Cartão branco com título opcional.
class SectionCard extends StatelessWidget {
  const SectionCard({super.key, this.title, this.trailing, required this.child, this.padding});

  final String? title;
  final Widget? trailing;
  final Widget child;
  final EdgeInsetsGeometry? padding;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: padding ?? const EdgeInsets.fromLTRB(18, 16, 18, 16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (title != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Row(
                  children: [
                    Expanded(
                      child: Text(title!, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15)),
                    ),
                    ?trailing,
                  ],
                ),
              ),
            child,
          ],
        ),
      ),
    );
  }
}

enum PillTone { pending, late, review, neutral }

class Pill extends StatelessWidget {
  const Pill(this.label, {super.key, this.icon, this.tone = PillTone.neutral});

  final String label;
  final IconData? icon;
  final PillTone tone;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final dark = Theme.of(context).brightness == Brightness.dark;
    final (fg, bg) = switch (tone) {
      PillTone.pending => (dark ? c.positive : FinanceColors.brand2, c.focus.withValues(alpha: 0.13)),
      PillTone.late => (c.negative, c.negative.withValues(alpha: 0.11)),
      PillTone.review => (c.warning, c.warningBg),
      PillTone.neutral => (c.ink2, c.field),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(999)),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[Icon(icon, size: 12, color: fg), const SizedBox(width: 4)],
          Text(
            label,
            style: TextStyle(color: fg, fontSize: 11, fontWeight: FontWeight.w600),
          ),
        ],
      ),
    );
  }
}

class CategoryAvatar extends StatelessWidget {
  const CategoryAvatar(this.category, {super.key, this.size = 42});

  final String category;
  final double size;

  @override
  Widget build(BuildContext context) {
    final color = categoryColor(category);
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: color.withValues(alpha: Theme.of(context).brightness == Brightness.dark ? 0.2 : 0.12),
        borderRadius: BorderRadius.circular(size * 0.3),
      ),
      child: Icon(categoryIcon(category), color: color, size: size * 0.5),
    );
  }
}

/// Linha de uma movimentação.
class TransactionTile extends StatelessWidget {
  const TransactionTile({super.key, required this.txn, this.onTap, this.showDate = false});

  final Txn txn;
  final VoidCallback? onTap;
  final bool showDate;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final late = txn.isPending && txn.effectiveDue.compareTo(isoDate(today())) < 0;
    final meta = [if (showDate) shortDate(txn.occurredOn), txn.category, ?txn.paymentMethod, ?txn.account].join(' · ');
    final pills = <Widget>[
      if (txn.isPending)
        Pill(
          late
              ? 'vencida ${shortDate(txn.effectiveDue)}'
              : '${txn.isIncome ? 'a receber' : 'vence'} ${shortDate(txn.effectiveDue)}',
          icon: Icons.schedule,
          tone: late ? PillTone.late : PillTone.pending,
        ),
      if (txn.needsReview) const Pill('revisar', icon: Icons.error_outline, tone: PillTone.review),
    ];

    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(14),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 9),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            CategoryAvatar(txn.category),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    txn.description,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(fontWeight: FontWeight.w600, fontSize: 15, color: c.ink),
                  ),
                  const SizedBox(height: 1),
                  Text(
                    meta,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(fontSize: 13, color: c.muted),
                  ),
                  if (pills.isNotEmpty) ...[
                    const SizedBox(height: 6),
                    Wrap(spacing: 6, runSpacing: 4, children: pills),
                  ],
                ],
              ),
            ),
            const SizedBox(width: 10),
            Padding(
              padding: const EdgeInsets.only(top: 10),
              child: Text(
                '${txn.isIncome ? '+' : '−'} ${money(txn.amountCents)}',
                style: TextStyle(
                  fontWeight: FontWeight.w600,
                  fontSize: 15,
                  color: txn.isIncome ? c.positive : c.ink,
                  fontFeatures: const [FontFeature.tabularFigures()],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class EmptyState extends StatelessWidget {
  const EmptyState({super.key, required this.icon, required this.title, required this.message});

  final IconData icon;
  final String title;
  final String message;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 28, horizontal: 12),
      child: Column(
        children: [
          Container(
            width: 52,
            height: 52,
            decoration: BoxDecoration(color: c.field, borderRadius: BorderRadius.circular(16)),
            child: Icon(icon, color: c.muted),
          ),
          const SizedBox(height: 12),
          Text(title, style: serif(size: 19, color: c.ink)),
          const SizedBox(height: 4),
          Text(
            message,
            textAlign: TextAlign.center,
            style: TextStyle(color: c.muted, fontSize: 14),
          ),
        ],
      ),
    );
  }
}

/// Faixa de aviso (vencidas, revisão).
class AlertBanner extends StatelessWidget {
  const AlertBanner({super.key, required this.text, this.danger = false, this.action, this.onTap});

  final String text;
  final bool danger;
  final String? action;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final fg = danger ? c.negative : c.warning;
    final bg = danger ? c.negative.withValues(alpha: 0.09) : c.warningBg;
    return Material(
      color: bg,
      borderRadius: BorderRadius.circular(16),
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          child: Row(
            children: [
              Icon(danger ? Icons.error_outline : Icons.fact_check_outlined, color: fg, size: 20),
              const SizedBox(width: 10),
              Expanded(
                child: Text(text, style: TextStyle(color: fg, fontSize: 14, height: 1.3)),
              ),
              if (action != null) ...[
                const SizedBox(width: 8),
                Text(
                  action!,
                  style: TextStyle(color: fg, fontWeight: FontWeight.w700, fontSize: 13),
                ),
                Icon(Icons.chevron_right, color: fg, size: 18),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

void showMessage(BuildContext context, String message, {bool error = false}) {
  final c = context.colors;
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(
      SnackBar(
        content: Row(
          children: [
            Icon(
              error ? Icons.error_outline : Icons.check_circle_outline,
              color: error ? c.negative : c.positive,
              size: 20,
            ),
            const SizedBox(width: 10),
            Expanded(child: Text(message)),
          ],
        ),
      ),
    );
}
