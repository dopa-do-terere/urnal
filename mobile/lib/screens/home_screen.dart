import 'package:flutter/material.dart';

import '../data/finance_repository.dart';
import '../theme.dart';
import 'capture_sheet.dart';
import 'dashboard_tab.dart';
import 'settings_tab.dart';
import 'transactions_tab.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key, required this.repo});

  final FinanceRepository repo;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  var _tab = 0;
  var _month = DateTime(DateTime.now().year, DateTime.now().month);
  var _filter = TxnFilter.month;

  void _setMonth(DateTime month) => setState(() => _month = month);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _tab,
        children: [
          DashboardTab(
            repo: widget.repo,
            month: _month,
            onMonthChanged: _setMonth,
            onShowReview: () => setState(() {
              _filter = TxnFilter.review;
              _tab = 1;
            }),
          ),
          TransactionsTab(
            repo: widget.repo,
            month: _month,
            onMonthChanged: _setMonth,
            filter: _filter,
            onFilterChanged: (f) => setState(() => _filter = f),
          ),
          SettingsTab(repo: widget.repo),
        ],
      ),
      floatingActionButton: _tab == 2
          ? null
          : FloatingActionButton.extended(
              onPressed: () => showCaptureSheet(context, widget.repo),
              backgroundColor: FinanceColors.brand,
              foregroundColor: const Color(0xFFF2FBE4),
              elevation: 2,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
              icon: const Icon(Icons.add, color: FinanceColors.lime),
              label: const Text('Registrar', style: TextStyle(fontWeight: FontWeight.w700)),
            ),
      bottomNavigationBar: DecoratedBox(
        decoration: BoxDecoration(
          border: Border(top: BorderSide(color: context.colors.line)),
        ),
        child: NavigationBar(
          selectedIndex: _tab,
          onDestinationSelected: (i) => setState(() => _tab = i),
          destinations: const [
            NavigationDestination(
              icon: Icon(Icons.space_dashboard_outlined),
              selectedIcon: Icon(Icons.space_dashboard),
              label: 'Início',
            ),
            NavigationDestination(
              icon: Icon(Icons.receipt_long_outlined),
              selectedIcon: Icon(Icons.receipt_long),
              label: 'Lançamentos',
            ),
            NavigationDestination(icon: Icon(Icons.tune_outlined), selectedIcon: Icon(Icons.tune), label: 'Ajustes'),
          ],
        ),
      ),
    );
  }
}
