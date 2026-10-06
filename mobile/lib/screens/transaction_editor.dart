import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../data/finance_repository.dart';
import '../models/txn.dart';
import '../theme.dart';
import '../util/categories.dart';
import '../util/format.dart';
import '../widgets/common.dart';

Future<void> openEditor(BuildContext context, FinanceRepository repo, Txn? txn) {
  return Navigator.of(context).push(
    MaterialPageRoute(
      fullscreenDialog: txn == null,
      builder: (_) => TransactionEditor(repo: repo, txn: txn),
    ),
  );
}

const _paymentMethods = [
  'Pix',
  'Cartão de crédito',
  'Cartão de débito',
  'Dinheiro',
  'Boleto',
  'Transferência',
  'Débito automático',
];

class TransactionEditor extends StatefulWidget {
  const TransactionEditor({super.key, required this.repo, this.txn});

  final FinanceRepository repo;
  final Txn? txn;

  @override
  State<TransactionEditor> createState() => _TransactionEditorState();
}

class _TransactionEditorState extends State<TransactionEditor> {
  final _form = GlobalKey<FormState>();
  late final TextEditingController _amount;
  late final TextEditingController _description;
  late final TextEditingController _counterparty;
  late final TextEditingController _method;
  late final TextEditingController _account;
  late final TextEditingController _notes;
  late String _kind;
  late String _status;
  late String _category;
  late String _occurredOn;
  String? _dueDate;
  var _saving = false;

  bool get _isNew => widget.txn == null;

  @override
  void initState() {
    super.initState();
    final t = widget.txn;
    _amount = TextEditingController(text: t == null ? '' : centsToInput(t.amountCents));
    _description = TextEditingController(text: t?.description ?? '');
    _counterparty = TextEditingController(text: t?.counterparty ?? '');
    _method = TextEditingController(text: t?.paymentMethod ?? '');
    _account = TextEditingController(text: t?.account ?? '');
    _notes = TextEditingController(text: t?.notes ?? '');
    _kind = t?.kind ?? 'expense';
    _status = t?.status ?? 'paid';
    _category = t?.category ?? 'Outros';
    _occurredOn = t?.occurredOn ?? isoDate(today());
    _dueDate = t?.dueDate;
  }

  @override
  void dispose() {
    for (final c in [_amount, _description, _counterparty, _method, _account, _notes]) {
      c.dispose();
    }
    super.dispose();
  }

  String? _nullIfEmpty(TextEditingController c) => c.text.trim().isEmpty ? null : c.text.trim();

  Txn _build({bool? needsReview}) {
    final base =
        widget.txn ??
        Txn(
          id: '',
          kind: _kind,
          status: _status,
          amountCents: 0,
          description: '',
          category: _category,
          occurredOn: _occurredOn,
        );
    return base.copyWith(
      kind: _kind,
      status: _status,
      amountCents: parseMoney(_amount.text) ?? 0,
      description: _description.text.trim(),
      category: _category,
      occurredOn: _occurredOn,
      dueDate: () => _dueDate,
      counterparty: () => _nullIfEmpty(_counterparty),
      paymentMethod: () => _nullIfEmpty(_method),
      account: () => _nullIfEmpty(_account),
      notes: () => _nullIfEmpty(_notes),
      needsReview: needsReview ?? false,
    );
  }

  Future<void> _run(Future<void> Function() action, String done) async {
    setState(() => _saving = true);
    try {
      await action();
      if (!mounted) return;
      showMessage(context, done);
      Navigator.of(context).pop();
    } catch (e) {
      if (!mounted) return;
      setState(() => _saving = false);
      showMessage(context, 'Não foi possível salvar: $e', error: true);
    }
  }

  void _save() {
    if (!_form.currentState!.validate()) return;
    final txn = _build();
    _run(
      () => _isNew ? widget.repo.create(txn) : widget.repo.update(txn),
      _isNew ? 'Lançamento registrado' : 'Lançamento atualizado',
    );
  }

  void _markPaid() {
    if (!_form.currentState!.validate()) return;
    final txn = _build().copyWith(status: 'paid', occurredOn: isoDate(today()));
    _run(() => widget.repo.update(txn), txn.isIncome ? 'Marcado como recebido' : 'Marcado como pago');
  }

  Future<void> _delete() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Excluir lançamento?'),
        content: const Text('Esta ação não pode ser desfeita.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancelar')),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            style: TextButton.styleFrom(foregroundColor: context.colors.negative),
            child: const Text('Excluir'),
          ),
        ],
      ),
    );
    if (ok == true) _run(() => widget.repo.delete(widget.txn!.id), 'Lançamento excluído');
  }

  Future<void> _pickDate({required bool due}) async {
    final current = due ? (_dueDate ?? _occurredOn) : _occurredOn;
    final picked = await showDatePicker(
      context: context,
      initialDate: parseIso(current),
      firstDate: DateTime(2000),
      lastDate: DateTime(today().year + 5, 12, 31),
    );
    if (picked == null) return;
    setState(() => due ? _dueDate = isoDate(picked) : _occurredOn = isoDate(picked));
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final txn = widget.txn;
    final categories = categoriesFor(_kind);
    final categoryOptions = categories.contains(_category) ? categories : [_category, ...categories];

    return Scaffold(
      appBar: AppBar(
        title: Text(_isNew ? 'Novo lançamento' : 'Lançamento'),
        actions: [
          if (!_isNew)
            IconButton(
              tooltip: 'Excluir',
              icon: Icon(Icons.delete_outline, color: c.negative),
              onPressed: _saving ? null : _delete,
            ),
        ],
      ),
      body: Form(
        key: _form,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 4, 20, 140),
          children: [
            SegmentedButton<String>(
              segments: const [
                ButtonSegment(value: 'expense', label: Text('Despesa'), icon: Icon(Icons.north_east, size: 18)),
                ButtonSegment(value: 'income', label: Text('Receita'), icon: Icon(Icons.south_west, size: 18)),
              ],
              selected: {_kind},
              showSelectedIcon: false,
              onSelectionChanged: (s) => setState(() {
                _kind = s.first;
                if (!categoriesFor(_kind).contains(_category)) {
                  _category = _kind == 'income' ? 'Outras receitas' : 'Outros';
                }
              }),
            ),
            const SizedBox(height: 18),
            Row(
              crossAxisAlignment: CrossAxisAlignment.baseline,
              textBaseline: TextBaseline.alphabetic,
              children: [
                Text(r'R$', style: serif(size: 24, color: c.muted)),
                const SizedBox(width: 10),
                Expanded(
                  child: TextFormField(
                    controller: _amount,
                    autofocus: _isNew,
                    keyboardType: const TextInputType.numberWithOptions(decimal: true),
                    inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[0-9.,]'))],
                    style: serif(size: 42, color: _kind == 'income' ? c.positive : c.ink),
                    decoration: InputDecoration(
                      hintText: '0,00',
                      hintStyle: serif(size: 42, color: c.line),
                      filled: false,
                      border: InputBorder.none,
                      enabledBorder: InputBorder.none,
                      focusedBorder: InputBorder.none,
                      contentPadding: EdgeInsets.zero,
                    ),
                    validator: (v) => parseMoney(v ?? '') == null ? 'Informe o valor' : null,
                  ),
                ),
              ],
            ),
            Divider(color: c.line),
            if (txn != null && txn.needsReview) ...[
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(color: c.warningBg, borderRadius: BorderRadius.circular(16)),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(Icons.fact_check_outlined, color: c.warning, size: 18),
                        const SizedBox(width: 8),
                        Text(
                          'Confira antes de confirmar',
                          style: TextStyle(color: c.warning, fontWeight: FontWeight.w700),
                        ),
                      ],
                    ),
                    if (txn.notes != null) ...[
                      const SizedBox(height: 6),
                      Text(txn.notes!, style: TextStyle(color: c.warning, fontSize: 13.5, height: 1.35)),
                    ],
                  ],
                ),
              ),
            ],
            const SizedBox(height: 18),
            TextFormField(
              controller: _description,
              textCapitalization: TextCapitalization.sentences,
              maxLength: 255,
              decoration: const InputDecoration(labelText: 'Descrição', counterText: ''),
              validator: (v) => (v ?? '').trim().isEmpty ? 'Informe a descrição' : null,
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              initialValue: _category,
              isExpanded: true,
              decoration: const InputDecoration(labelText: 'Categoria'),
              items: [
                for (final cat in categoryOptions)
                  DropdownMenuItem(
                    value: cat,
                    child: Row(
                      children: [
                        CategoryAvatar(cat, size: 26),
                        const SizedBox(width: 10),
                        Flexible(child: Text(cat, overflow: TextOverflow.ellipsis)),
                      ],
                    ),
                  ),
              ],
              onChanged: (v) => setState(() => _category = v ?? _category),
            ),
            const SizedBox(height: 16),
            _Label('Situação'),
            SegmentedButton<String>(
              segments: [
                ButtonSegment(value: 'paid', label: Text(_kind == 'income' ? 'Recebido' : 'Pago')),
                const ButtonSegment(value: 'pending', label: Text('Pendente')),
              ],
              selected: {_status},
              showSelectedIcon: false,
              onSelectionChanged: (s) => setState(() => _status = s.first),
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: _DateField(
                    label: _status == 'pending' ? 'Data prevista' : 'Data',
                    value: fullDate(_occurredOn),
                    onTap: () => _pickDate(due: false),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _DateField(
                    label: 'Vencimento',
                    value: _dueDate == null ? 'Sem vencimento' : fullDate(_dueDate!),
                    onTap: () => _pickDate(due: true),
                    onClear: _dueDate == null ? null : () => setState(() => _dueDate = null),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _counterparty,
              textCapitalization: TextCapitalization.words,
              decoration: InputDecoration(labelText: _kind == 'income' ? 'Quem pagou' : 'Loja, pessoa ou empresa'),
            ),
            const SizedBox(height: 16),
            _Label('Forma de pagamento'),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final m in _paymentMethods)
                  ChoiceChip(
                    label: Text(m),
                    selected: _method.text == m,
                    onSelected: (on) => setState(() => _method.text = on ? m : ''),
                  ),
              ],
            ),
            const SizedBox(height: 16),
            TextFormField(
              controller: _account,
              decoration: const InputDecoration(labelText: 'Conta ou cartão', hintText: 'Ex.: Nubank crédito'),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _notes,
              minLines: 2,
              maxLines: 5,
              decoration: const InputDecoration(labelText: 'Observações', alignLabelWithHint: true),
            ),
            if (txn != null && txn.items.isNotEmpty) ...[
              const SizedBox(height: 20),
              SectionCard(
                title: 'Itens da nota (${txn.items.length})',
                child: Column(
                  children: [
                    for (final item in txn.items)
                      Padding(
                        padding: const EdgeInsets.symmetric(vertical: 6),
                        child: Row(
                          children: [
                            Expanded(
                              child: Text(
                                item.quantity != null && item.quantity != 1
                                    ? '${item.description}  ×${item.quantity!.toStringAsFixed(item.quantity! % 1 == 0 ? 0 : 2)}'
                                    : item.description,
                                style: TextStyle(fontSize: 13.5, color: c.ink2),
                              ),
                            ),
                            Text(money(item.totalCents), style: TextStyle(fontSize: 13.5, color: c.ink)),
                          ],
                        ),
                      ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
      bottomNavigationBar: SafeArea(
        child: Container(
          padding: const EdgeInsets.fromLTRB(20, 12, 20, 12),
          decoration: BoxDecoration(
            color: c.background,
            border: Border(top: BorderSide(color: c.line)),
          ),
          child: Row(
            children: [
              if (txn != null && txn.isPending) ...[
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _saving ? null : _markPaid,
                    icon: const Icon(Icons.check, size: 18),
                    label: Text(txn.isIncome ? 'Recebido hoje' : 'Pago hoje'),
                  ),
                ),
                const SizedBox(width: 12),
              ],
              Expanded(
                child: FilledButton(
                  onPressed: _saving ? null : _save,
                  child: _saving
                      ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                      : Text(txn?.needsReview == true ? 'Confirmar' : 'Salvar'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Label extends StatelessWidget {
  const _Label(this.text);
  final String text;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 8, left: 2),
    child: Text(
      text,
      style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: context.colors.muted),
    ),
  );
}

class _DateField extends StatelessWidget {
  const _DateField({required this.label, required this.value, required this.onTap, this.onClear});

  final String label;
  final String value;
  final VoidCallback onTap;
  final VoidCallback? onClear;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: InputDecorator(
        decoration: InputDecoration(
          labelText: label,
          suffixIcon: onClear == null
              ? Icon(Icons.calendar_today_outlined, size: 18, color: c.muted)
              : IconButton(icon: const Icon(Icons.close, size: 18), onPressed: onClear),
        ),
        child: Text(value, style: TextStyle(fontSize: 15, color: c.ink)),
      ),
    );
  }
}
