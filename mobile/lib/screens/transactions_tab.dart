import 'package:flutter/material.dart';

import '../data/finance_repository.dart';
import '../models/txn.dart';
import '../theme.dart';
import '../util/format.dart';
import '../widgets/common.dart';
import 'transaction_editor.dart';

enum TxnFilter { month, review, pending }

class TransactionsTab extends StatefulWidget {
  const TransactionsTab({
    super.key,
    required this.repo,
    required this.month,
    required this.onMonthChanged,
    required this.filter,
    required this.onFilterChanged,
  });

  final FinanceRepository repo;
  final DateTime month;
  final ValueChanged<DateTime> onMonthChanged;
  final TxnFilter filter;
  final ValueChanged<TxnFilter> onFilterChanged;

  @override
  State<TransactionsTab> createState() => _TransactionsTabState();
}

class _TransactionsTabState extends State<TransactionsTab> {
  final _search = TextEditingController();
  var _query = '';

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  Stream<List<Txn>> get _stream => switch (widget.filter) {
    TxnFilter.month => widget.repo.month(widget.month),
    TxnFilter.review => widget.repo.toReview(),
    TxnFilter.pending => widget.repo.pending(),
  };

  bool _matches(Txn t) {
    if (_query.isEmpty) return true;
    final q = _query.toLowerCase();
    return [
      t.description,
      t.counterparty,
      t.category,
      t.notes,
      t.account,
    ].any((v) => v != null && v.toLowerCase().contains(q));
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return SafeArea(
      bottom: false,
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 12, 16, 8),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    'Lançamentos',
                    style: serif(size: 24, weight: FontWeight.w600, color: c.ink),
                  ),
                ),
                if (widget.filter == TxnFilter.month)
                  MonthSwitcher(month: widget.month, onChanged: widget.onMonthChanged),
              ],
            ),
          ),
          SizedBox(
            height: 44,
            child: ListView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 16),
              children: [
                for (final (filter, label, icon) in [
                  (TxnFilter.month, 'Do mês', Icons.calendar_month_outlined),
                  (TxnFilter.review, 'Para revisar', Icons.fact_check_outlined),
                  (TxnFilter.pending, 'Pendentes', Icons.schedule),
                ])
                  Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: ChoiceChip(
                      avatar: Icon(icon, size: 16),
                      label: Text(label),
                      selected: widget.filter == filter,
                      onSelected: (_) => widget.onFilterChanged(filter),
                    ),
                  ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 6, 16, 4),
            child: TextField(
              controller: _search,
              onChanged: (v) => setState(() => _query = v.trim()),
              textInputAction: TextInputAction.search,
              decoration: InputDecoration(
                hintText: 'Buscar por descrição, loja, categoria',
                prefixIcon: Icon(Icons.search, color: c.muted),
                suffixIcon: _query.isEmpty
                    ? null
                    : IconButton(
                        icon: const Icon(Icons.close),
                        onPressed: () => setState(() {
                          _search.clear();
                          _query = '';
                        }),
                      ),
                contentPadding: const EdgeInsets.symmetric(vertical: 10),
              ),
            ),
          ),
          Expanded(
            child: StreamBuilder<List<Txn>>(
              stream: _stream,
              builder: (context, snap) {
                if (snap.hasError) {
                  return EmptyState(
                    icon: Icons.cloud_off_outlined,
                    title: 'Não foi possível carregar',
                    message: '${snap.error}',
                  );
                }
                if (!snap.hasData) return const Center(child: CircularProgressIndicator());
                final items = snap.data!.where(_matches).toList();
                if (items.isEmpty) return _empty();
                return _GroupedList(
                  items: items,
                  groupByDue: widget.filter == TxnFilter.pending,
                  onTap: (t) => openEditor(context, widget.repo, t),
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _empty() {
    if (_query.isNotEmpty) {
      return const EmptyState(icon: Icons.search_off, title: 'Nada encontrado', message: 'Tente outro termo.');
    }
    return switch (widget.filter) {
      TxnFilter.month => const EmptyState(
        icon: Icons.receipt_long_outlined,
        title: 'Nenhum lançamento',
        message: 'Toque em Registrar para enviar uma foto, um PDF ou escrever uma mensagem.',
      ),
      TxnFilter.review => const EmptyState(
        icon: Icons.verified_outlined,
        title: 'Nada para revisar',
        message: 'Tudo o que foi lido automaticamente já foi conferido.',
      ),
      TxnFilter.pending => const EmptyState(
        icon: Icons.event_available_outlined,
        title: 'Sem pendências',
        message: 'Nenhuma conta aguardando pagamento.',
      ),
    };
  }
}

class _GroupedList extends StatelessWidget {
  const _GroupedList({required this.items, required this.onTap, this.groupByDue = false});

  final List<Txn> items;
  final ValueChanged<Txn> onTap;
  final bool groupByDue;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final groups = <String, List<Txn>>{};
    for (final t in items) {
      groups.putIfAbsent(groupByDue ? t.effectiveDue : t.occurredOn, () => []).add(t);
    }
    final entries = groups.entries.toList();
    return ListView.builder(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 120),
      itemCount: entries.length,
      itemBuilder: (context, i) {
        final day = entries[i].key;
        final list = entries[i].value;
        final net = list.where((t) => !t.isPending).fold<int>(0, (s, t) => s + t.signedCents);
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(6, 14, 6, 4),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      (groupByDue ? 'Vence ${shortDate(day)}' : dayLabel(day)).toUpperCase(),
                      style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700, letterSpacing: 0.7, color: c.muted),
                    ),
                  ),
                  if (net != 0)
                    Text(
                      '${net > 0 ? '+' : '−'} ${money(net.abs())}',
                      style: TextStyle(fontSize: 12, color: c.muted, fontWeight: FontWeight.w500),
                    ),
                ],
              ),
            ),
            Card(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
                child: Column(
                  children: [
                    for (final (j, t) in list.indexed) ...[
                      if (j > 0) Divider(height: 1, indent: 60, color: c.line.withValues(alpha: 0.7)),
                      TransactionTile(txn: t, onTap: () => onTap(t), showDate: groupByDue),
                    ],
                  ],
                ),
              ),
            ),
          ],
        );
      },
    );
  }
}
