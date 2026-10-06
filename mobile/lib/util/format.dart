import 'package:intl/intl.dart';

final _currency = NumberFormat.currency(locale: 'pt_BR', symbol: r'R$', decimalDigits: 2);

/// R$ 1.234,56 a partir de centavos.
String money(int cents) => _currency.format(cents / 100);

/// "1.234,56" (sem símbolo), para campos de edição.
String centsToInput(int cents) {
  final reais = cents ~/ 100;
  final rest = (cents % 100).toString().padLeft(2, '0');
  return '${NumberFormat.decimalPattern('pt_BR').format(reais)},$rest';
}

/// Converte "45,90", "R$ 1.234,56", "1234.5" em centavos. Nulo se inválido.
int? parseMoney(String input) {
  var text = input.replaceAll('R\$', '').replaceAll(RegExp(r'\s'), '').replaceAll('-', '');
  if (text.isEmpty) return null;
  final comma = text.lastIndexOf(',');
  final dot = text.lastIndexOf('.');
  if (comma >= 0 && dot >= 0) {
    text = comma > dot ? text.replaceAll('.', '').replaceAll(',', '.') : text.replaceAll(',', '');
  } else if (comma >= 0) {
    text = text.replaceAll(',', '.');
  } else if (RegExp(r'^\d{1,3}(\.\d{3})+$').hasMatch(text)) {
    text = text.replaceAll('.', '');
  }
  if (!RegExp(r'^\d+(\.\d+)?$').hasMatch(text)) return null;
  final parts = text.split('.');
  final reais = int.parse(parts[0]);
  var decimals = parts.length > 1 ? parts[1] : '0';
  // arredonda meio para cima na terceira casa
  final third = decimals.length > 2 ? int.parse(decimals[2]) : 0;
  decimals = '${decimals}00'.substring(0, 2);
  var cents = reais * 100 + int.parse(decimals);
  if (third >= 5) cents += 1;
  return cents;
}

/// Datas são guardadas como "AAAA-MM-DD".
String isoDate(DateTime d) =>
    '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

DateTime parseIso(String iso) {
  final p = iso.split('-').map(int.parse).toList();
  return DateTime(p[0], p[1], p[2]);
}

DateTime today() {
  final now = DateTime.now();
  return DateTime(now.year, now.month, now.day);
}

String capitalize(String s) => s.isEmpty ? s : s[0].toUpperCase() + s.substring(1);

String monthLabel(DateTime month) => capitalize(DateFormat("MMMM 'de' y", 'pt_BR').format(month));

String shortDate(String iso) => DateFormat("d 'de' MMM", 'pt_BR').format(parseIso(iso)).replaceAll('.', '');

String fullDate(String iso) => DateFormat('dd/MM/yyyy', 'pt_BR').format(parseIso(iso));

/// "Hoje", "Ontem" ou "qua, 15 de outubro".
String dayLabel(String iso) {
  final d = parseIso(iso);
  final t = today();
  if (d == t) return 'Hoje';
  if (d == t.subtract(const Duration(days: 1))) return 'Ontem';
  return DateFormat("EEE, d 'de' MMMM", 'pt_BR').format(d).replaceAll('.', '');
}

/// "Vence hoje", "Vence em 3 dias", "Venceu há 2 dias".
String dueLabel(String iso) {
  final days = parseIso(iso).difference(today()).inDays;
  if (days == 0) return 'Vence hoje';
  if (days == 1) return 'Vence amanhã';
  if (days > 1) return 'Vence em $days dias';
  if (days == -1) return 'Venceu ontem';
  return 'Venceu há ${-days} dias';
}
