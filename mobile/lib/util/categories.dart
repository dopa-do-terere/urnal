import 'package:flutter/material.dart';

/// Mesmas categorias de financas_core/categories.py.
const expenseCategories = [
  'Mercado',
  'Alimentação',
  'Moradia',
  'Contas de consumo',
  'Transporte',
  'Saúde',
  'Educação',
  'Lazer',
  'Compras',
  'Serviços e assinaturas',
  'Impostos e taxas',
  'Transferências',
  'Outros',
];

const incomeCategories = [
  'Salário',
  'Vendas e serviços prestados',
  'Rendimentos',
  'Reembolsos',
  'Transferências',
  'Outras receitas',
];

const _colors = <String, Color>{
  'Mercado': Color(0xFF0F766E),
  'Alimentação': Color(0xFFEA580C),
  'Moradia': Color(0xFFB45309),
  'Contas de consumo': Color(0xFF0284C7),
  'Transporte': Color(0xFF4F46E5),
  'Saúde': Color(0xFFDB2777),
  'Educação': Color(0xFF7C3AED),
  'Lazer': Color(0xFF65A30D),
  'Compras': Color(0xFFC026D3),
  'Serviços e assinaturas': Color(0xFF0891B2),
  'Impostos e taxas': Color(0xFFDC2626),
  'Transferências': Color(0xFF64748B),
  'Salário': Color(0xFF15803D),
  'Vendas e serviços prestados': Color(0xFF059669),
  'Rendimentos': Color(0xFFCA8A04),
  'Reembolsos': Color(0xFF0D9488),
};

const _icons = <String, IconData>{
  'Mercado': Icons.shopping_basket_outlined,
  'Alimentação': Icons.restaurant_outlined,
  'Moradia': Icons.home_outlined,
  'Contas de consumo': Icons.bolt_outlined,
  'Transporte': Icons.directions_car_outlined,
  'Saúde': Icons.favorite_border,
  'Educação': Icons.school_outlined,
  'Lazer': Icons.local_activity_outlined,
  'Compras': Icons.shopping_bag_outlined,
  'Serviços e assinaturas': Icons.subscriptions_outlined,
  'Impostos e taxas': Icons.account_balance_outlined,
  'Transferências': Icons.swap_horiz,
  'Salário': Icons.work_outline,
  'Vendas e serviços prestados': Icons.storefront_outlined,
  'Rendimentos': Icons.trending_up,
  'Reembolsos': Icons.replay,
};

Color categoryColor(String category) => _colors[category] ?? const Color(0xFF78716C);

IconData categoryIcon(String category) => _icons[category] ?? Icons.category_outlined;

List<String> categoriesFor(String kind) => kind == 'income' ? incomeCategories : expenseCategories;
