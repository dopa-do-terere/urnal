import 'package:financas/models/txn.dart';
import 'package:financas/util/format.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:intl/date_symbol_data_local.dart';

void main() {
  setUpAll(() => initializeDateFormatting('pt_BR'));

  group('parseMoney', () {
    final cases = {
      '45,90': 4590,
      'R\$ 1.234,56': 123456,
      '1,234.56': 123456,
      '1.234': 123400,
      '10.5': 1050,
      '7': 700,
      '0,005': 1,
      '-12,30': 1230,
    };
    cases.forEach((input, cents) {
      test('"$input" -> $cents', () => expect(parseMoney(input), cents));
    });
    test('inválidos', () {
      expect(parseMoney(''), isNull);
      expect(parseMoney('abc'), isNull);
      expect(parseMoney('1,2,3'), isNull);
    });
  });

  test('money e centsToInput', () {
    expect(money(123456), 'R\$ 1.234,56');
    expect(centsToInput(123456), '1.234,56');
    expect(centsToInput(5), '0,05');
    expect(parseMoney(centsToInput(987654321)), 987654321);
  });

  test('datas ISO', () {
    expect(isoDate(DateTime(2026, 3, 7)), '2026-03-07');
    expect(parseIso('2026-03-07'), DateTime(2026, 3, 7));
    expect(monthLabel(DateTime(2026, 10)), 'Outubro de 2026');
    expect(dayLabel(isoDate(today())), 'Hoje');
    expect(dueLabel(isoDate(today().add(const Duration(days: 3)))), 'Vence em 3 dias');
    expect(dueLabel(isoDate(today().subtract(const Duration(days: 2)))), 'Venceu há 2 dias');
  });

  test('Txn.fromMap lê o formato gravado pelas Cloud Functions', () {
    final t = Txn.fromMap('x1', {
      'kind': 'expense',
      'status': 'pending',
      'amount_cents': 18990,
      'description': 'Boleto Itaú',
      'category': 'Outros',
      'occurred_on': '2026-11-10',
      'due_date': '2026-11-10',
      'needs_review': true,
      'source': 'boleto',
      'external_id': '3419',
      'items': [
        {'description': 'ARROZ', 'quantity': 2.0, 'unit_price_cents': 2550, 'total_cents': 5100},
      ],
    });
    expect(t.isPending, isTrue);
    expect(t.signedCents, -18990);
    expect(t.items.single.totalCents, 5100);
    expect(t.toEditableMap().containsKey('external_id'), isFalse);
  });

  test('MonthSummary separa pagos, pendentes e categorias', () {
    Txn tx(String kind, int cents, String cat, {String status = 'paid'}) => Txn(
      id: '$cents',
      kind: kind,
      status: status,
      amountCents: cents,
      description: cat,
      category: cat,
      occurredOn: '2026-10-01',
    );
    final s = MonthSummary.from([
      tx('income', 500000, 'Salário'),
      tx('expense', 1000, 'Mercado'),
      tx('expense', 3000, 'Moradia'),
      tx('expense', 500, 'Mercado'),
      tx('expense', 9999, 'Educação', status: 'pending'),
      tx('income', 2000, 'Outras receitas', status: 'pending'),
    ]);
    expect(s.incomeCents, 500000);
    expect(s.expenseCents, 4500);
    expect(s.balanceCents, 495500);
    expect(s.pendingExpenseCents, 9999);
    expect(s.pendingIncomeCents, 2000);
    expect(s.byCategory.map((e) => e.key), ['Moradia', 'Mercado']);
    expect(s.byCategory.last.value, 1500);
  });

  test('IngestResult.fromMap', () {
    final r = IngestResult.fromMap({
      'created': [
        {'id': 'a', 'kind': 'expense', 'amount_cents': 100, 'description': 'X', 'occurred_on': '2026-10-01'},
      ],
      'updated': [],
      'duplicates': [],
      'warnings': ['ok'],
    });
    expect(r.savedSomething, isTrue);
    expect(r.created.single.id, 'a');
    expect(r.warnings, ['ok']);
  });
}
