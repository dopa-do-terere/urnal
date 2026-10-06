import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../data/finance_repository.dart';
import '../theme.dart';
import '../widgets/common.dart';

class SettingsTab extends StatefulWidget {
  const SettingsTab({super.key, required this.repo});

  final FinanceRepository repo;

  @override
  State<SettingsTab> createState() => _SettingsTabState();
}

class _SettingsTabState extends State<SettingsTab> {
  final _doc = TextEditingController();

  @override
  void dispose() {
    _doc.dispose();
    super.dispose();
  }

  String _format(String digits) {
    if (digits.length == 11) {
      return '${digits.substring(0, 3)}.${digits.substring(3, 6)}.${digits.substring(6, 9)}-${digits.substring(9)}';
    }
    if (digits.length == 14) {
      return '${digits.substring(0, 2)}.${digits.substring(2, 5)}.${digits.substring(5, 8)}/'
          '${digits.substring(8, 12)}-${digits.substring(12)}';
    }
    return digits;
  }

  Future<void> _add(List<String> current) async {
    final digits = _doc.text.replaceAll(RegExp(r'\D'), '');
    if (digits.length != 11 && digits.length != 14) {
      showMessage(context, 'Informe um CPF (11 dígitos) ou CNPJ (14 dígitos).', error: true);
      return;
    }
    if (current.contains(digits)) return;
    await widget.repo.setOwnerDocuments([...current, digits]);
    _doc.clear();
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return SafeArea(
      bottom: false,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 120),
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(4, 0, 4, 16),
            child: Text(
              'Ajustes',
              style: serif(size: 24, weight: FontWeight.w600, color: c.ink),
            ),
          ),
          SectionCard(
            child: Row(
              children: [
                Container(
                  width: 44,
                  height: 44,
                  decoration: BoxDecoration(color: FinanceColors.brand, borderRadius: BorderRadius.circular(14)),
                  child: const Icon(Icons.person_outline, color: FinanceColors.lime),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Conectado como', style: TextStyle(fontSize: 12, color: c.muted)),
                      Text(
                        widget.repo.userLabel,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(fontWeight: FontWeight.w600, color: c.ink),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          StreamBuilder<List<String>>(
            stream: widget.repo.ownerDocuments(),
            builder: (context, snap) {
              final docs = snap.data ?? const <String>[];
              return SectionCard(
                title: 'Meus CPF e CNPJ',
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Text(
                      'Usados para saber se uma nota fiscal é uma venda sua (receita) ou uma compra (despesa).',
                      style: TextStyle(color: c.muted, fontSize: 13.5, height: 1.35),
                    ),
                    const SizedBox(height: 12),
                    if (docs.isNotEmpty)
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: [
                          for (final d in docs)
                            InputChip(
                              label: Text(_format(d)),
                              onDeleted: () => widget.repo.setOwnerDocuments([...docs]..remove(d)),
                            ),
                        ],
                      ),
                    if (docs.isNotEmpty) const SizedBox(height: 12),
                    Row(
                      children: [
                        Expanded(
                          child: TextField(
                            controller: _doc,
                            keyboardType: TextInputType.number,
                            inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[0-9./-]'))],
                            decoration: const InputDecoration(hintText: 'CPF ou CNPJ'),
                            onSubmitted: (_) => _add(docs),
                          ),
                        ),
                        const SizedBox(width: 8),
                        IconButton.filled(onPressed: () => _add(docs), icon: const Icon(Icons.add)),
                      ],
                    ),
                  ],
                ),
              );
            },
          ),
          const SizedBox(height: 16),
          SectionCard(
            title: 'Como a leitura funciona',
            child: Column(
              children: [
                _HowRow(
                  icon: Icons.verified_outlined,
                  title: 'XML de NF-e e linha digitável',
                  text: 'Lidos direto, sem IA, com conferência dos dígitos verificadores.',
                ),
                _HowRow(
                  icon: Icons.auto_awesome_outlined,
                  title: 'Fotos, prints, PDFs e mensagens',
                  text: 'Lidos por IA. Valores de boleto e chaves de nota são sempre conferidos.',
                ),
                _HowRow(
                  icon: Icons.copy_all_outlined,
                  title: 'Sem lançamentos repetidos',
                  text: 'O mesmo arquivo, nota ou boleto não entra duas vezes. O comprovante dá baixa no boleto.',
                ),
                _HowRow(
                  icon: Icons.fact_check_outlined,
                  title: 'Fila de revisão',
                  text: 'Leituras incertas ou parecidas com outro lançamento ficam marcadas para você conferir.',
                ),
              ],
            ),
          ),
          const SizedBox(height: 20),
          OutlinedButton.icon(
            onPressed: widget.repo.signOut,
            icon: Icon(Icons.logout, color: c.negative, size: 18),
            label: Text('Sair da conta', style: TextStyle(color: c.negative)),
          ),
        ],
      ),
    );
  }
}

class _HowRow extends StatelessWidget {
  const _HowRow({required this.icon, required this.title, required this.text});

  final IconData icon;
  final String title;
  final String text;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 20, color: c.focus),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: TextStyle(fontWeight: FontWeight.w600, color: c.ink, fontSize: 14),
                ),
                const SizedBox(height: 2),
                Text(text, style: TextStyle(color: c.muted, fontSize: 13, height: 1.35)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
