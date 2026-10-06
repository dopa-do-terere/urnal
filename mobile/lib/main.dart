import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:cloud_functions/cloud_functions.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_storage/firebase_storage.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:intl/intl.dart';

import 'data/demo_repository.dart';
import 'data/finance_repository.dart';
import 'data/firebase_repository.dart';
import 'firebase_options.dart';
import 'screens/home_screen.dart';
import 'screens/login_screen.dart';
import 'theme.dart';

/// `--dart-define=DEMO=true`: dados de exemplo, sem Firebase.
const demoMode = bool.fromEnvironment('DEMO');

/// `--dart-define=USE_EMULATORS=true`: usa os emuladores locais do Firebase.
/// No emulador Android, use também `--dart-define=EMULATOR_HOST=10.0.2.2`.
const useEmulators = bool.fromEnvironment('USE_EMULATORS');
const emulatorHost = String.fromEnvironment('EMULATOR_HOST', defaultValue: 'localhost');

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  Intl.defaultLocale = 'pt_BR';
  await initializeDateFormatting('pt_BR');

  if (!demoMode) {
    await Firebase.initializeApp(options: DefaultFirebaseOptions.currentPlatform);
    if (useEmulators) {
      await FirebaseAuth.instance.useAuthEmulator(emulatorHost, 9099);
      FirebaseFirestore.instance.useFirestoreEmulator(emulatorHost, 8080);
      await FirebaseStorage.instance.useStorageEmulator(emulatorHost, 9199);
      FirebaseFunctions.instanceFor(region: functionsRegion).useFunctionsEmulator(emulatorHost, 5001);
    }
  }

  runApp(FinanceApp(demoRepository: demoMode ? DemoFinanceRepository() : null));
}

class FinanceApp extends StatelessWidget {
  const FinanceApp({super.key, this.demoRepository});

  /// Quando presente, o app usa este repositório e dispensa login.
  final FinanceRepository? demoRepository;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Finanças',
      debugShowCheckedModeBanner: false,
      theme: buildTheme(Brightness.light),
      darkTheme: buildTheme(Brightness.dark),
      locale: const Locale('pt', 'BR'),
      supportedLocales: const [Locale('pt', 'BR')],
      localizationsDelegates: const [
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      home: demoRepository != null ? HomeScreen(repo: demoRepository!) : const AuthGate(),
    );
  }
}

class AuthGate extends StatelessWidget {
  const AuthGate({super.key});

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<User?>(
      stream: FirebaseAuth.instance.authStateChanges(),
      builder: (context, snap) {
        if (snap.connectionState == ConnectionState.waiting) {
          return const Scaffold(body: Center(child: CircularProgressIndicator()));
        }
        final user = snap.data;
        if (user == null) return const LoginScreen();
        return HomeScreen(key: ValueKey(user.uid), repo: FirebaseFinanceRepository(user));
      },
    );
  }
}
