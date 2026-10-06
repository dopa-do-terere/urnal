/// Movimentação financeira, como gravada em users/{uid}/transactions.
class Txn {
  const Txn({
    required this.id,
    required this.kind,
    required this.status,
    required this.amountCents,
    required this.description,
    required this.category,
    required this.occurredOn,
    this.dueDate,
    this.counterparty,
    this.paymentMethod,
    this.account,
    this.notes,
    this.needsReview = false,
    this.source = 'manual',
    this.externalId,
    this.documentId,
    this.items = const [],
  });

  final String id;
  final String kind; // expense | income
  final String status; // paid | pending
  final int amountCents;
  final String description;
  final String category;
  final String occurredOn; // AAAA-MM-DD
  final String? dueDate;
  final String? counterparty;
  final String? paymentMethod;
  final String? account;
  final String? notes;
  final bool needsReview;
  final String source;
  final String? externalId;
  final String? documentId;
  final List<TxnItem> items;

  bool get isIncome => kind == 'income';
  bool get isPending => status == 'pending';
  String get effectiveDue => dueDate ?? occurredOn;
  int get signedCents => isIncome ? amountCents : -amountCents;

  factory Txn.fromMap(String id, Map<String, dynamic> m) {
    return Txn(
      id: id,
      kind: m['kind'] as String? ?? 'expense',
      status: m['status'] as String? ?? 'paid',
      amountCents: (m['amount_cents'] as num?)?.toInt() ?? 0,
      description: m['description'] as String? ?? '',
      category: m['category'] as String? ?? 'Outros',
      occurredOn: m['occurred_on'] as String? ?? '1970-01-01',
      dueDate: m['due_date'] as String?,
      counterparty: m['counterparty'] as String?,
      paymentMethod: m['payment_method'] as String?,
      account: m['account'] as String?,
      notes: m['notes'] as String?,
      needsReview: m['needs_review'] as bool? ?? false,
      source: m['source'] as String? ?? 'manual',
      externalId: m['external_id'] as String?,
      documentId: m['document_id'] as String?,
      items: [
        for (final item in (m['items'] as List?) ?? const [])
          if (item is Map) TxnItem.fromMap(Map<String, dynamic>.from(item)),
      ],
    );
  }

  /// Campos editáveis pelo app (as regras do Firestore validam o resto).
  Map<String, dynamic> toEditableMap() => {
    'kind': kind,
    'status': status,
    'amount_cents': amountCents,
    'description': description,
    'category': category,
    'occurred_on': occurredOn,
    'due_date': dueDate,
    'counterparty': counterparty,
    'payment_method': paymentMethod,
    'account': account,
    'notes': notes,
    'needs_review': needsReview,
  };

  Txn copyWith({
    String? kind,
    String? status,
    int? amountCents,
    String? description,
    String? category,
    String? occurredOn,
    String? Function()? dueDate,
    String? Function()? counterparty,
    String? Function()? paymentMethod,
    String? Function()? account,
    String? Function()? notes,
    bool? needsReview,
  }) {
    return Txn(
      id: id,
      kind: kind ?? this.kind,
      status: status ?? this.status,
      amountCents: amountCents ?? this.amountCents,
      description: description ?? this.description,
      category: category ?? this.category,
      occurredOn: occurredOn ?? this.occurredOn,
      dueDate: dueDate != null ? dueDate() : this.dueDate,
      counterparty: counterparty != null ? counterparty() : this.counterparty,
      paymentMethod: paymentMethod != null ? paymentMethod() : this.paymentMethod,
      account: account != null ? account() : this.account,
      notes: notes != null ? notes() : this.notes,
      needsReview: needsReview ?? this.needsReview,
      source: source,
      externalId: externalId,
      documentId: documentId,
      items: items,
    );
  }
}

class TxnItem {
  const TxnItem({required this.description, required this.totalCents, this.quantity, this.unitPriceCents});

  final String description;
  final int totalCents;
  final double? quantity;
  final int? unitPriceCents;

  factory TxnItem.fromMap(Map<String, dynamic> m) => TxnItem(
    description: m['description'] as String? ?? 'Item',
    totalCents: (m['total_cents'] as num?)?.toInt() ?? 0,
    quantity: (m['quantity'] as num?)?.toDouble(),
    unitPriceCents: (m['unit_price_cents'] as num?)?.toInt(),
  );
}

/// Resposta das funções ingest_text / ingest_file.
class IngestResult {
  const IngestResult({
    this.created = const [],
    this.updated = const [],
    this.duplicates = const [],
    this.warnings = const [],
  });

  final List<Txn> created;
  final List<Txn> updated;
  final List<Txn> duplicates;
  final List<String> warnings;

  bool get savedSomething => created.isNotEmpty || updated.isNotEmpty;

  factory IngestResult.fromMap(Map<String, dynamic> m) {
    List<Txn> list(String key) => [
      for (final raw in (m[key] as List?) ?? const [])
        if (raw is Map) Txn.fromMap(raw['id'] as String? ?? '', Map<String, dynamic>.from(raw)),
    ];
    return IngestResult(
      created: list('created'),
      updated: list('updated'),
      duplicates: list('duplicates'),
      warnings: [for (final w in (m['warnings'] as List?) ?? const []) w.toString()],
    );
  }
}

/// Resumo do mês calculado no app.
class MonthSummary {
  const MonthSummary({
    required this.incomeCents,
    required this.expenseCents,
    required this.pendingExpenseCents,
    required this.pendingIncomeCents,
    required this.byCategory,
  });

  final int incomeCents;
  final int expenseCents;
  final int pendingExpenseCents;
  final int pendingIncomeCents;
  final List<MapEntry<String, int>> byCategory; // despesas pagas, maior primeiro

  int get balanceCents => incomeCents - expenseCents;

  factory MonthSummary.from(List<Txn> monthTxns) {
    var income = 0, expense = 0, pendingExpense = 0, pendingIncome = 0;
    final categories = <String, int>{};
    for (final t in monthTxns) {
      if (t.isPending) {
        t.isIncome ? pendingIncome += t.amountCents : pendingExpense += t.amountCents;
      } else if (t.isIncome) {
        income += t.amountCents;
      } else {
        expense += t.amountCents;
        categories[t.category] = (categories[t.category] ?? 0) + t.amountCents;
      }
    }
    final sorted = categories.entries.toList()..sort((a, b) => b.value.compareTo(a.value));
    return MonthSummary(
      incomeCents: income,
      expenseCents: expense,
      pendingExpenseCents: pendingExpense,
      pendingIncomeCents: pendingIncome,
      byCategory: sorted,
    );
  }
}
