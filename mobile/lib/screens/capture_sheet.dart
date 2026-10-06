import 'dart:typed_data';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../data/finance_repository.dart';
import '../models/txn.dart';
import '../theme.dart';
import '../util/format.dart';
import '../widgets/common.dart';
import 'transaction_editor.dart';

Future<void> showCaptureSheet(BuildContext context, FinanceRepository repo) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    builder: (_) => CaptureSheet(repo: repo),
  );
}

/// Arquivo a enviar, já em memória.
class _Pending {
  _Pending(this.name, this.bytes, this.mime);
  final String name;
  final Uint8List bytes;
  final String? mime;
}

/// Resultado de um envio (arquivo ou mensagem).
class _Outcome {
  _Outcome(this.label, {this.result, this.error});
  final String label;
  final IngestResult? result;
  final String? error;
}

class CaptureSheet extends StatefulWidget {
  const CaptureSheet({super.key, required this.repo});

  final FinanceRepository repo;

  @override
  State<CaptureSheet> createState() => _CaptureSheetState();
}

class _CaptureSheetState extends State<CaptureSheet> {
  final _text = TextEditingController();
  final _picker = ImagePicker();

  var _busy = false;
  var _stage = '';
  double? _progress;
  List<_Outcome>? _outcomes;

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  Future<void> _sendText() async {
    final text = _text.text.trim();
    if (text.isEmpty) return;
    FocusScope.of(context).unfocus();
    setState(() {
      _busy = true;
      _stage = 'Entendendo sua mensagem…';
      _progress = null;
    });
    _Outcome outcome;
    try {
      outcome = _Outcome('Mensagem', result: await widget.repo.ingestText(text));
      _text.clear();
    } catch (e) {
      outcome = _Outcome('Mensagem', error: '$e');
    }
    if (mounted) {
      setState(() {
        _busy = false;
        _outcomes = [outcome];
      });
    }
  }

  Future<void> _sendFiles(List<_Pending> files) async {
    if (files.isEmpty) return;
    final outcomes = <_Outcome>[];
    setState(() => _busy = true);
    for (final (i, file) in files.indexed) {
      final prefix = files.length > 1 ? '${i + 1} de ${files.length} · ' : '';
      setState(() {
        _stage = '${prefix}Enviando ${file.name}';
        _progress = 0;
      });
      try {
        final result = await widget.repo.ingestFile(
          file.bytes,
          file.name,
          mimeType: file.mime,
          onProgress: (p) {
            if (!mounted) return;
            setState(() {
              _progress = p >= 1 ? null : p;
              if (p >= 1) _stage = '${prefix}Lendo o documento…';
            });
          },
        );
        outcomes.add(_Outcome(file.name, result: result));
      } catch (e) {
        outcomes.add(_Outcome(file.name, error: '$e'));
      }
    }
    if (mounted) {
      setState(() {
        _busy = false;
        _outcomes = outcomes;
      });
    }
  }

  Future<void> _camera() async {
    final photo = await _picker.pickImage(source: ImageSource.camera, imageQuality: 85, maxWidth: 2400);
    if (photo == null) return;
    await _sendFiles([_Pending(photo.name, await photo.readAsBytes(), photo.mimeType ?? 'image/jpeg')]);
  }

  Future<void> _gallery() async {
    final images = await _picker.pickMultiImage(imageQuality: 85, maxWidth: 2400);
    await _sendFiles([
      for (final img in images) _Pending(img.name, await img.readAsBytes(), img.mimeType ?? guessMime(img.name)),
    ]);
  }

  Future<void> _files() async {
    final picked = await FilePicker.pickFiles(
      type: FileType.custom,
      allowedExtensions: const ['pdf', 'xml', 'jpg', 'jpeg', 'png', 'txt'],
      allowMultiple: true,
      withData: true,
    );
    if (picked == null) return;
    await _sendFiles([
      for (final f in picked.files)
        if (f.bytes != null) _Pending(f.name, f.bytes!, guessMime(f.name)),
    ]);
  }

  void _manual() {
    final navigator = Navigator.of(context);
    navigator.pop();
    openEditor(navigator.context, widget.repo, null);
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedPadding(
      duration: const Duration(milliseconds: 150),
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: AnimatedSize(
        duration: const Duration(milliseconds: 220),
        curve: Curves.easeOutCubic,
        alignment: Alignment.topCenter,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 0, 20, 24),
          child: _busy ? _buildBusy() : (_outcomes != null ? _buildResults() : _buildIdle()),
        ),
      ),
    );
  }

  Widget _buildIdle() {
    final c = context.colors;
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          'Registrar',
          style: serif(size: 26, weight: FontWeight.w600, color: c.ink),
        ),
        const SizedBox(height: 4),
        Text(
          'Envie o documento ou escreva. A leitura é automática e os dados conferíveis são validados.',
          style: TextStyle(color: c.muted, fontSize: 14, height: 1.35),
        ),
        const SizedBox(height: 18),
        Row(
          children: [
            Expanded(
              child: _ActionTile(
                icon: Icons.photo_camera_outlined,
                title: 'Fotografar',
                subtitle: 'Cupom, boleto, nota',
                highlight: true,
                onTap: _camera,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _ActionTile(
                icon: Icons.photo_library_outlined,
                title: 'Prints e fotos',
                subtitle: 'Comprovantes, Pix',
                onTap: _gallery,
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        Row(
          children: [
            Expanded(
              child: _ActionTile(
                icon: Icons.description_outlined,
                title: 'PDF ou XML',
                subtitle: 'NF-e, fatura, extrato',
                onTap: _files,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _ActionTile(
                icon: Icons.edit_outlined,
                title: 'Digitar',
                subtitle: 'Lançamento manual',
                onTap: _manual,
              ),
            ),
          ],
        ),
        const SizedBox(height: 16),
        TextField(
          controller: _text,
          minLines: 1,
          maxLines: 4,
          textCapitalization: TextCapitalization.sentences,
          textInputAction: TextInputAction.send,
          onSubmitted: (_) => _sendText(),
          decoration: InputDecoration(
            hintText: 'gastei 45,90 no iFood ontem…',
            prefixIcon: Icon(Icons.chat_bubble_outline, color: c.muted, size: 20),
            suffixIcon: Padding(
              padding: const EdgeInsets.all(6),
              child: IconButton.filled(
                onPressed: _sendText,
                icon: const Icon(Icons.arrow_upward, size: 20),
                tooltip: 'Registrar mensagem',
              ),
            ),
          ),
        ),
        const SizedBox(height: 8),
        Text(
          'Também aceita a linha digitável de um boleto colada aqui.',
          textAlign: TextAlign.center,
          style: TextStyle(color: c.muted, fontSize: 12),
        ),
      ],
    );
  }

  Widget _buildBusy() {
    final c = context.colors;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 28),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 64,
            height: 64,
            decoration: BoxDecoration(color: FinanceColors.brand, borderRadius: BorderRadius.circular(20)),
            child: const Padding(
              padding: EdgeInsets.all(18),
              child: CircularProgressIndicator(strokeWidth: 2.5, color: FinanceColors.lime),
            ),
          ),
          const SizedBox(height: 18),
          Text(
            _stage,
            textAlign: TextAlign.center,
            style: TextStyle(fontWeight: FontWeight.w600, color: c.ink),
          ),
          const SizedBox(height: 6),
          Text('Isso leva alguns segundos', style: TextStyle(color: c.muted, fontSize: 13)),
          const SizedBox(height: 18),
          ClipRRect(
            borderRadius: BorderRadius.circular(99),
            child: LinearProgressIndicator(value: _progress, minHeight: 6, backgroundColor: c.field),
          ),
        ],
      ),
    );
  }

  Widget _buildResults() {
    final c = context.colors;
    final outcomes = _outcomes!;
    final saved = outcomes.fold<int>(
      0,
      (s, o) => s + (o.result?.created.length ?? 0) + (o.result?.updated.length ?? 0),
    );
    final failed = outcomes.where((o) => o.error != null).length;
    final title = saved > 0
        ? (saved == 1 ? '1 lançamento registrado' : '$saved lançamentos registrados')
        : (failed > 0 ? 'Não foi possível registrar' : 'Nada novo registrado');

    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          children: [
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: (saved > 0 ? c.positive : (failed > 0 ? c.negative : c.warning)).withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(
                saved > 0 ? Icons.check : (failed > 0 ? Icons.close : Icons.info_outline),
                color: saved > 0 ? c.positive : (failed > 0 ? c.negative : c.warning),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                title,
                style: serif(size: 21, weight: FontWeight.w600, color: c.ink),
              ),
            ),
          ],
        ),
        const SizedBox(height: 14),
        ConstrainedBox(
          constraints: BoxConstraints(maxHeight: MediaQuery.sizeOf(context).height * 0.5),
          child: ListView(
            shrinkWrap: true,
            children: [for (final o in outcomes) _OutcomeCard(outcome: o, repo: widget.repo)],
          ),
        ),
        const SizedBox(height: 16),
        Row(
          children: [
            Expanded(
              child: OutlinedButton(
                onPressed: () => setState(() => _outcomes = null),
                child: const Text('Registrar outro'),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: FilledButton(onPressed: () => Navigator.pop(context), child: const Text('Concluir')),
            ),
          ],
        ),
      ],
    );
  }
}

class _ActionTile extends StatelessWidget {
  const _ActionTile({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
    this.highlight = false,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;
  final bool highlight;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final fg = highlight ? Colors.white : c.ink;
    return Material(
      color: highlight ? FinanceColors.brand : c.field,
      borderRadius: BorderRadius.circular(20),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(20),
        child: Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(20),
            border: highlight ? null : Border.all(color: c.line),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 36,
                height: 36,
                decoration: BoxDecoration(
                  color: highlight ? FinanceColors.lime.withValues(alpha: 0.16) : c.card,
                  borderRadius: BorderRadius.circular(11),
                ),
                child: Icon(icon, size: 20, color: highlight ? FinanceColors.lime : c.ink2),
              ),
              const SizedBox(height: 14),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: TextStyle(fontWeight: FontWeight.w700, fontSize: 15, color: fg),
                  ),
                  Text(
                    subtitle,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(fontSize: 12, color: highlight ? const Color(0xBFEAF5EF) : c.muted),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _OutcomeCard extends StatelessWidget {
  const _OutcomeCard({required this.outcome, required this.repo});

  final _Outcome outcome;
  final FinanceRepository repo;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final r = outcome.result;
    Widget line(String text, Color color, IconData icon) => Padding(
      padding: const EdgeInsets.only(top: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 16, color: color),
          const SizedBox(width: 8),
          Expanded(
            child: Text(text, style: TextStyle(fontSize: 13.5, color: color, height: 1.3)),
          ),
        ],
      ),
    );

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
      decoration: BoxDecoration(
        color: c.field,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: c.line),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            outcome.label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13, color: c.muted),
          ),
          if (outcome.error != null) line(outcome.error!, c.negative, Icons.error_outline),
          if (r != null) ...[
            for (final t in r.created) _SavedRow(txn: t, repo: repo),
            for (final t in r.updated)
              line('Baixa no pagamento: ${t.description} · ${money(t.amountCents)}', c.positive, Icons.task_alt),
            for (final t in r.duplicates) line('Já registrado: ${t.description}', c.muted, Icons.history),
            for (final w in r.warnings) line(w, c.warning, Icons.info_outline),
          ],
        ],
      ),
    );
  }
}

class _SavedRow extends StatelessWidget {
  const _SavedRow({required this.txn, required this.repo});

  final Txn txn;
  final FinanceRepository repo;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Row(
        children: [
          CategoryAvatar(txn.category, size: 34),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  txn.description,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(fontWeight: FontWeight.w600, color: c.ink),
                ),
                Text(
                  [txn.category, fullDate(txn.occurredOn)].join(' · '),
                  style: TextStyle(fontSize: 12, color: c.muted),
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                '${txn.isIncome ? '+' : '−'} ${money(txn.amountCents)}',
                style: TextStyle(fontWeight: FontWeight.w600, color: txn.isIncome ? c.positive : c.ink),
              ),
              if (txn.needsReview) const Pill('revisar', tone: PillTone.review),
            ],
          ),
        ],
      ),
    );
  }
}
