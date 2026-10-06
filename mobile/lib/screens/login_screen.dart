import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/material.dart';

import '../theme.dart';
import '../widgets/common.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _form = GlobalKey<FormState>();
  final _email = TextEditingController();
  final _password = TextEditingController();
  var _creating = false;
  var _busy = false;
  var _obscure = true;
  String? _error;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  String _message(FirebaseAuthException e) => switch (e.code) {
    'invalid-email' => 'E-mail inválido.',
    'user-disabled' => 'Esta conta foi desativada.',
    'user-not-found' || 'wrong-password' || 'invalid-credential' => 'E-mail ou senha incorretos.',
    'email-already-in-use' => 'Já existe uma conta com este e-mail.',
    'weak-password' => 'Use uma senha com pelo menos 6 caracteres.',
    'too-many-requests' => 'Muitas tentativas. Aguarde um pouco e tente de novo.',
    'network-request-failed' => 'Sem conexão com a internet.',
    _ => e.message ?? 'Não foi possível entrar.',
  };

  Future<void> _submit() async {
    if (!_form.currentState!.validate()) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    final auth = FirebaseAuth.instance;
    try {
      if (_creating) {
        await auth.createUserWithEmailAndPassword(email: _email.text.trim(), password: _password.text);
      } else {
        await auth.signInWithEmailAndPassword(email: _email.text.trim(), password: _password.text);
      }
    } on FirebaseAuthException catch (e) {
      setState(() => _error = _message(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _reset() async {
    final email = _email.text.trim();
    if (!email.contains('@')) {
      setState(() => _error = 'Digite seu e-mail acima para receber o link.');
      return;
    }
    try {
      await FirebaseAuth.instance.sendPasswordResetEmail(email: email);
      if (mounted) showMessage(context, 'Enviamos um link para $email.');
    } on FirebaseAuthException catch (e) {
      setState(() => _error = _message(e));
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Scaffold(
      body: SingleChildScrollView(
        child: Column(
          children: [
            Container(
              width: double.infinity,
              padding: EdgeInsets.fromLTRB(28, MediaQuery.paddingOf(context).top + 48, 28, 64),
              decoration: const BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [Color(0xFF14503F), FinanceColors.brand, Color(0xFF0A2621)],
                ),
                borderRadius: BorderRadius.vertical(bottom: Radius.circular(36)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const AppLogo(size: 52),
                  const SizedBox(height: 28),
                  Text(
                    'Suas finanças,\norganizadas sozinhas.',
                    style: serif(size: 32, color: Colors.white, height: 1.15),
                  ),
                  const SizedBox(height: 12),
                  const Text(
                    'Fotografe a nota, mande o print do Pix ou cole o boleto. O resto é com a gente.',
                    style: TextStyle(color: Color(0xBFEAF5EF), fontSize: 15, height: 1.4),
                  ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(24, 28, 24, 32),
              child: Form(
                key: _form,
                child: AutofillGroup(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Text(
                        _creating ? 'Criar conta' : 'Entrar',
                        style: serif(size: 24, weight: FontWeight.w600, color: c.ink),
                      ),
                      const SizedBox(height: 18),
                      TextFormField(
                        controller: _email,
                        keyboardType: TextInputType.emailAddress,
                        autofillHints: const [AutofillHints.email],
                        textInputAction: TextInputAction.next,
                        decoration: const InputDecoration(labelText: 'E-mail', prefixIcon: Icon(Icons.mail_outline)),
                        validator: (v) => (v ?? '').contains('@') ? null : 'Informe um e-mail válido',
                      ),
                      const SizedBox(height: 12),
                      TextFormField(
                        controller: _password,
                        obscureText: _obscure,
                        autofillHints: [_creating ? AutofillHints.newPassword : AutofillHints.password],
                        onFieldSubmitted: (_) => _submit(),
                        decoration: InputDecoration(
                          labelText: 'Senha',
                          prefixIcon: const Icon(Icons.lock_outline),
                          suffixIcon: IconButton(
                            icon: Icon(_obscure ? Icons.visibility_outlined : Icons.visibility_off_outlined),
                            onPressed: () => setState(() => _obscure = !_obscure),
                          ),
                        ),
                        validator: (v) => (v ?? '').length >= 6 ? null : 'Mínimo de 6 caracteres',
                      ),
                      if (_error != null) ...[
                        const SizedBox(height: 12),
                        Text(_error!, style: TextStyle(color: c.negative, fontSize: 13.5)),
                      ],
                      const SizedBox(height: 20),
                      FilledButton(
                        onPressed: _busy ? null : _submit,
                        child: _busy
                            ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                            : Text(_creating ? 'Criar conta' : 'Entrar'),
                      ),
                      const SizedBox(height: 8),
                      if (!_creating) TextButton(onPressed: _reset, child: const Text('Esqueci minha senha')),
                      TextButton(
                        onPressed: () => setState(() {
                          _creating = !_creating;
                          _error = null;
                        }),
                        child: Text(_creating ? 'Já tenho conta' : 'Criar uma conta'),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Marca do app: "S" verde-limão sobre o verde da marca (mesmo desenho do ícone).
class AppLogo extends StatelessWidget {
  const AppLogo({super.key, this.size = 40});

  final double size;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: FinanceColors.brand,
        borderRadius: BorderRadius.circular(size * 0.3),
        border: Border.all(color: Colors.white.withValues(alpha: 0.12)),
      ),
      child: CustomPaint(painter: _LogoPainter()),
    );
  }
}

class _LogoPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final k = size.width / 32;
    final path = Path()
      ..moveTo(9 * k, 20.5 * k)
      ..cubicTo(11.2 * k, 22.5 * k, 13.6 * k, 23.5 * k, 16 * k, 23.5 * k)
      ..cubicTo(19.6 * k, 23.5 * k, 22 * k, 21.7 * k, 22 * k, 19.1 * k)
      ..cubicTo(22 * k, 13.5 * k, 9.4 * k, 16.5 * k, 9.4 * k, 11.1 * k)
      ..cubicTo(9.4 * k, 8.6 * k, 11.8 * k, 6.8 * k, 15.4 * k, 6.8 * k)
      ..cubicTo(17.7 * k, 6.8 * k, 19.8 * k, 7.6 * k, 21.6 * k, 9.2 * k);
    canvas.drawPath(
      path,
      Paint()
        ..color = FinanceColors.lime
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.6 * k
        ..strokeCap = StrokeCap.round,
    );
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
