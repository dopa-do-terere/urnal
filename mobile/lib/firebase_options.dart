// Este arquivo é substituído ao rodar `flutterfire configure` (veja o
// README). Enquanto isso, o app só funciona em modo demonstração:
//   flutter run --dart-define=DEMO=true
import 'package:firebase_core/firebase_core.dart';

class DefaultFirebaseOptions {
  static FirebaseOptions get currentPlatform {
    throw UnsupportedError(
      'Firebase ainda não configurado. Rode `flutterfire configure` na pasta mobile/ '
      'ou use --dart-define=DEMO=true.',
    );
  }
}
