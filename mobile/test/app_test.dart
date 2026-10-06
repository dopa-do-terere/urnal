import 'package:financas/data/demo_repository.dart';
import 'package:financas/main.dart';
import 'package:financas/models/txn.dart';
import 'package:financas/util/format.dart';
import 'package:financas/widgets/common.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:intl/intl.dart';

void main() {
  setUpAll(() async {
    Intl.defaultLocale = 'pt_BR';
    await initializeDateFormatting('pt_BR');
  });

  Txn tx(String kind, int cents, String desc, String cat, {String status = 'paid', int day = 0, bool review = false}) {
    final d = isoDate(today().add(Duration(days: day)));
    return Txn(
      id: '',
      kind: kind,
      status: status,
      amountCents: cents,
      description: desc,
      category: cat,
      occurredOn: d,
      dueDate: status == 'pending' ? d : null,
      needsReview: review,
    );
  }

  Future<DemoFinanceRepository> pumpApp(WidgetTester tester, List<Txn> items) async {
    tester.view.physicalSize = const Size(1170, 2532);
    tester.view.devicePixelRatio = 3;
    addTearDown(tester.view.reset);
    final repo = DemoFinanceRepository(seed: false);
    for (final t in items) {
      await repo.create(t);
    }
    await tester.pumpWidget(FinanceApp(demoRepository: repo));
    await tester.pumpAndSettle();
    return repo;
  }

  testWidgets('painel mostra saldo, pendências e revisão', (tester) async {
    await pumpApp(tester, [
      tx('income', 500000, 'Salário', 'Salário'),
      tx('expense', 120050, 'Aluguel', 'Moradia'),
      tx('expense', 23417, 'Conta de luz', 'Contas de consumo', status: 'pending', day: 2, review: true),
    ]);

    expect(find.text(money(379950)), findsOneWidget);
    expect(find.text('Conta de luz'), findsOneWidget);
    expect(find.textContaining('precisa de revisão'), findsOneWidget);
    await tester.scrollUntilVisible(find.text('Moradia'), 300, scrollable: find.byType(Scrollable).first);
    expect(find.text('Moradia'), findsOneWidget);
  });

  testWidgets('mensagem registrada pela folha de captura', (tester) async {
    await pumpApp(tester, []);
    await tester.tap(find.text('Registrar'));
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField).last, 'gastei 45,90 no mercado');
    await tester.tap(find.byTooltip('Registrar mensagem'));
    await tester.pump(const Duration(milliseconds: 700));
    await tester.pumpAndSettle();

    expect(find.text('1 lançamento registrado'), findsOneWidget);
    await tester.tap(find.text('Concluir'));
    await tester.pumpAndSettle();
    expect(find.textContaining('precisa de revisão'), findsOneWidget);
  });

  testWidgets('lançamento manual aparece na lista', (tester) async {
    final repo = await pumpApp(tester, []);
    await tester.tap(find.text('Registrar'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Digitar'));
    await tester.pumpAndSettle();

    expect(find.text('Novo lançamento'), findsOneWidget);
    await tester.enterText(find.byType(TextFormField).at(0), '89,90');
    await tester.enterText(find.byType(TextFormField).at(1), 'Farmácia');
    await tester.tap(find.text('Salvar'));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Lançamentos'));
    await tester.pumpAndSettle();
    expect(find.text('Farmácia'), findsOneWidget);
    expect(find.descendant(of: find.byType(TransactionTile), matching: find.text('− ${money(8990)}')), findsOneWidget);

    final saved = await repo.month(today()).first;
    expect(saved.single.amountCents, 8990);
    expect(saved.single.source, 'manual');
  });

  testWidgets('valor obrigatório no editor', (tester) async {
    await pumpApp(tester, []);
    await tester.tap(find.text('Registrar'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Digitar'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Salvar'));
    await tester.pumpAndSettle();
    expect(find.text('Informe o valor'), findsOneWidget);
    expect(find.text('Informe a descrição'), findsOneWidget);
  });

  testWidgets('marcar conta como paga', (tester) async {
    final repo = await pumpApp(tester, [
      tx('expense', 12000, 'Internet', 'Contas de consumo', status: 'pending', day: 1),
    ]);
    await tester.tap(find.text('Internet'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Pago hoje'));
    await tester.pumpAndSettle();

    final pending = await repo.pending().first;
    expect(pending, isEmpty);
    final month = await repo.month(today()).first;
    expect(month.single.status, 'paid');
    expect(month.single.occurredOn, isoDate(today()));
  });
}
