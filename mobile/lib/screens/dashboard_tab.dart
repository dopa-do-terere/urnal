import 'package:flutter/material.dart';

import '../data/finance_repository.dart';
import '../models/txn.dart';
import '../theme.dart';
import '../util/categories.dart';
import '../util/format.dart';
import '../widgets/common.dart';
import 'transaction_editor.dart';

class DashboardTab extends StatelessWidget {
  const DashboardTab({
    super.key,
    required this.repo,
    required this.month,
    required this.onMonthChanged,
    required this.onShowReview,
  });

  final FinanceRepository repo;
  final DateTime month;
  final ValueChanged<DateTime> onMonthChanged;
  final VoidCallback onShowReview;

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<List<Txn>>(
      stream: repo.month(month),
      builder: (context, monthSnap) => StreamBuilder<List<Txn>>(
        stream: repo.pending(),
        builder: (context, pendingSnap) => StreamBuilder<List<Txn>>(
          stream: repo.toReview(),
          builder: (context, reviewSnap) {
            final loading = !monthSnap.hasData;
            final summary = MonthSummary.from(monthSnap.data ?? const []);
            final pending = pendingSnap.data ?? const <Txn>[];
            final review = reviewSnap.data ?? const <Txn>[];
            final todayIso = isoDate(today());
            final limit = isoDate(today().add(const Duration(days: 15)));
            final overdue = pending.where((t) => t.effectiveDue.compareTo(todayIso) < 0).toList();
            final upcoming = pending.where((t) => t.effectiveDue.compareTo(limit) <= 0).toList();

            return CustomScrollView(
              slivers: [
                SliverToBoxAdapter(
                  child: _Header(month: month, onMonthChanged: onMonthChanged),
                ),
                SliverPadding(
                  padding: const EdgeInsets.fromLTRB(16, 4, 16, 120),
                  sliver: SliverList.list(
                    children: [
                      _HeroCard(summary: summary, loading: loading),
                      if (overdue.isNotEmpty) ...[
                        const SizedBox(height: 12),
                        AlertBanner(
                          danger: true,
                          text: overdue.length == 1
                              ? '1 conta vencida: ${money(overdue.first.amountCents)}'
                              : '${overdue.length} contas vencidas: '
                                    '${money(overdue.fold(0, (s, t) => s + t.amountCents))}',
                          action: 'Ver',
                          onTap: () => openEditor(context, repo, overdue.first),
                        ),
                      ],
                      if (review.isNotEmpty) ...[
                        const SizedBox(height: 10),
                        AlertBanner(
                          text: review.length == 1
                              ? '1 lançamento lido automaticamente precisa de revisão'
                              : '${review.length} lançamentos lidos automaticamente precisam de revisão',
                          action: 'Revisar',
                          onTap: onShowReview,
                        ),
                      ],
                      const SizedBox(height: 16),
                      SectionCard(
                        title: 'Próximos vencimentos',
                        child: upcoming.isEmpty
                            ? const EmptyState(
                                icon: Icons.event_available_outlined,
                                title: 'Tudo em dia',
                                message: 'Nenhuma conta vencida ou vencendo nos próximos 15 dias.',
                              )
                            : Column(
                                children: [
                                  for (final (i, t) in upcoming.take(6).indexed) ...[
                                    if (i > 0) const Divider(height: 1),
                                    _DueRow(txn: t, onTap: () => openEditor(context, repo, t)),
                                  ],
                                ],
                              ),
                      ),
                      const SizedBox(height: 16),
                      SectionCard(
                        title: 'Para onde foi o dinheiro',
                        child: summary.byCategory.isEmpty
                            ? const EmptyState(
                                icon: Icons.donut_large_outlined,
                                title: 'Nada gasto ainda',
                                message: 'As despesas pagas do mês aparecem aqui, por categoria.',
                              )
                            : _CategoryBreakdown(entries: summary.byCategory),
                      ),
                    ],
                  ),
                ),
              ],
            );
          },
        ),
      ),
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({required this.month, required this.onMonthChanged});

  final DateTime month;
  final ValueChanged<DateTime> onMonthChanged;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final hour = DateTime.now().hour;
    final greeting = hour < 12 ? 'Bom dia' : (hour < 18 ? 'Boa tarde' : 'Boa noite');
    return SafeArea(
      bottom: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 12, 16, 14),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(greeting, style: TextStyle(color: c.muted, fontSize: 13)),
                  Text(
                    'Suas finanças',
                    style: serif(size: 24, weight: FontWeight.w600, color: c.ink),
                  ),
                ],
              ),
            ),
            MonthSwitcher(month: month, onChanged: onMonthChanged),
          ],
        ),
      ),
    );
  }
}

class _HeroCard extends StatelessWidget {
  const _HeroCard({required this.summary, required this.loading});

  final MonthSummary summary;
  final bool loading;

  @override
  Widget build(BuildContext context) {
    const soft = Color(0xBFEAF5EF);
    final flow = summary.incomeCents + summary.expenseCents;
    final inShare = flow == 0 ? 0.0 : summary.incomeCents / flow;
    final negative = summary.balanceCents < 0;

    return Container(
      clipBehavior: Clip.antiAlias,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(26),
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF14503F), FinanceColors.brand, Color(0xFF0A2621)],
          stops: [0, 0.55, 1],
        ),
        boxShadow: const [BoxShadow(color: Color(0x400F3D34), blurRadius: 30, offset: Offset(0, 16))],
      ),
      child: Stack(
        clipBehavior: Clip.none,
        children: [
          Positioned(
            right: -50,
            top: -70,
            child: Container(
              width: 180,
              height: 180,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: RadialGradient(colors: [FinanceColors.lime.withValues(alpha: 0.16), Colors.transparent]),
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(22, 22, 22, 18),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'SALDO DO MÊS',
                  style: TextStyle(color: soft, fontSize: 11.5, fontWeight: FontWeight.w600, letterSpacing: 1.1),
                ),
                const SizedBox(height: 6),
                AnimatedSwitcher(
                  duration: const Duration(milliseconds: 250),
                  child: Text(
                    loading ? '—' : money(summary.balanceCents),
                    key: ValueKey(summary.balanceCents),
                    style: serif(size: 40, color: negative ? const Color(0xFFFFC2B8) : Colors.white, height: 1.1),
                  ),
                ),
                const SizedBox(height: 16),
                ClipRRect(
                  borderRadius: BorderRadius.circular(99),
                  child: SizedBox(
                    height: 8,
                    child: LayoutBuilder(
                      builder: (context, box) => Stack(
                        children: [
                          Container(color: Colors.white.withValues(alpha: 0.12)),
                          AnimatedContainer(
                            duration: const Duration(milliseconds: 500),
                            curve: Curves.easeOutCubic,
                            width: flow == 0 ? 0 : box.maxWidth * inShare,
                            decoration: BoxDecoration(
                              color: FinanceColors.lime,
                              borderRadius: BorderRadius.circular(99),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 10),
                Wrap(
                  spacing: 18,
                  runSpacing: 6,
                  children: [
                    _Legend(color: FinanceColors.lime, label: 'Entradas', value: money(summary.incomeCents)),
                    _Legend(
                      color: Colors.white.withValues(alpha: 0.5),
                      label: 'Saídas',
                      value: money(summary.expenseCents),
                    ),
                  ],
                ),
                const SizedBox(height: 18),
                Row(
                  children: [
                    Expanded(
                      child: _MiniStat(
                        icon: Icons.schedule,
                        label: 'A pagar',
                        value: money(summary.pendingExpenseCents),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: _MiniStat(
                        icon: Icons.south_west,
                        label: 'A receber',
                        value: money(summary.pendingIncomeCents),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _Legend extends StatelessWidget {
  const _Legend({required this.color, required this.label, required this.value});

  final Color color;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 8,
          height: 8,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 6),
        Text('$label ', style: const TextStyle(color: Color(0xBFEAF5EF), fontSize: 12.5)),
        Text(
          value,
          style: const TextStyle(color: Colors.white, fontSize: 12.5, fontWeight: FontWeight.w600),
        ),
      ],
    );
  }
}

class _MiniStat extends StatelessWidget {
  const _MiniStat({required this.icon, required this.label, required this.value});

  final IconData icon;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.07),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.white.withValues(alpha: 0.08)),
      ),
      child: Row(
        children: [
          Container(
            width: 32,
            height: 32,
            decoration: BoxDecoration(
              color: FinanceColors.lime.withValues(alpha: 0.14),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(icon, size: 17, color: FinanceColors.lime),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(color: Color(0xBFEAF5EF), fontSize: 11),
                ),
                FittedBox(
                  fit: BoxFit.scaleDown,
                  alignment: Alignment.centerLeft,
                  child: Text(
                    value,
                    style: const TextStyle(color: Colors.white, fontSize: 15, fontWeight: FontWeight.w600),
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

class _DueRow extends StatelessWidget {
  const _DueRow({required this.txn, required this.onTap});

  final Txn txn;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final due = parseIso(txn.effectiveDue);
    final late = txn.effectiveDue.compareTo(isoDate(today())) < 0;
    final accent = late ? c.negative : c.ink;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 10),
        child: Row(
          children: [
            Container(
              width: 46,
              height: 48,
              decoration: BoxDecoration(
                color: late ? c.negative.withValues(alpha: 0.1) : c.field,
                borderRadius: BorderRadius.circular(13),
              ),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    '${due.day}'.padLeft(2, '0'),
                    style: TextStyle(fontSize: 17, fontWeight: FontWeight.w700, color: accent, height: 1.1),
                  ),
                  Text(
                    shortDate(txn.effectiveDue).split(' ').last.toUpperCase(),
                    style: TextStyle(
                      fontSize: 10,
                      fontWeight: FontWeight.w600,
                      letterSpacing: 0.6,
                      color: late ? c.negative : c.muted,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    txn.description,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14.5, color: c.ink),
                  ),
                  Text(
                    txn.isIncome
                        ? 'A receber · ${dueLabel(txn.effectiveDue).toLowerCase()}'
                        : dueLabel(txn.effectiveDue),
                    style: TextStyle(fontSize: 12.5, color: late ? c.negative : c.muted),
                  ),
                ],
              ),
            ),
            Text(
              '${txn.isIncome ? '+ ' : ''}${money(txn.amountCents)}',
              style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14.5, color: txn.isIncome ? c.positive : c.ink),
            ),
          ],
        ),
      ),
    );
  }
}

class _CategoryBreakdown extends StatelessWidget {
  const _CategoryBreakdown({required this.entries});

  final List<MapEntry<String, int>> entries;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final total = entries.fold<int>(0, (s, e) => s + e.value);
    return Column(
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(99),
          child: SizedBox(
            height: 12,
            child: Row(
              children: [
                for (final (i, e) in entries.indexed) ...[
                  if (i > 0) const SizedBox(width: 2),
                  Expanded(
                    flex: (e.value * 1000 ~/ total).clamp(1, 1000),
                    child: Container(color: categoryColor(e.key)),
                  ),
                ],
              ],
            ),
          ),
        ),
        const SizedBox(height: 10),
        for (final (i, e) in entries.indexed) ...[
          if (i > 0) Divider(height: 1, color: c.line.withValues(alpha: 0.6)),
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 9),
            child: Row(
              children: [
                Container(
                  width: 10,
                  height: 10,
                  decoration: BoxDecoration(color: categoryColor(e.key), borderRadius: BorderRadius.circular(3)),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(e.key, style: TextStyle(fontSize: 14, color: c.ink)),
                ),
                Text('${(e.value * 100 / total).round()}%', style: TextStyle(fontSize: 12, color: c.muted)),
                const SizedBox(width: 12),
                SizedBox(
                  width: 96,
                  child: Text(
                    money(e.value),
                    textAlign: TextAlign.right,
                    style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13.5, color: c.ink),
                  ),
                ),
              ],
            ),
          ),
        ],
      ],
    );
  }
}
