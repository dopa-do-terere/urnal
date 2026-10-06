# Assistente de Finanças

App de celular (Flutter) com backend no Firebase que registra suas
movimentações financeiras a partir do que você mandar: foto de cupom ou nota,
print de comprovante de Pix, PDF de boleto ou fatura, XML de NF-e, linha
digitável ou uma mensagem como _"gastei 45,90 no iFood ontem no Nubank"_.

```
 Celular (Flutter)                      Firebase
 ┌─────────────────────┐   arquivo    ┌──────────────────────────────┐
 │ câmera / galeria /  │ ───────────► │ Storage  users/{uid}/uploads │
 │ PDF / XML / texto   │              └──────────────┬───────────────┘
 │                     │   chamada    ┌──────────────▼───────────────┐   ┌────────────┐
 │                     │ ───────────► │ Cloud Functions (Python)     │──►│ OpenRouter │
 │                     │              │ ingest_file / ingest_text    │   │ (IA)       │
 │                     │              │ parsers NF-e e boleto, dedup │   └────────────┘
 │                     │  tempo real  └──────────────┬───────────────┘
 │ painel, lista,      │ ◄─────────── ┌──────────────▼───────────────┐
 │ edição, revisão     │ ───────────► │ Firestore users/{uid}/...    │
 └─────────────────────┘   edições    └──────────────────────────────┘
```

## O que ele faz

| Entrada | Como é lida |
| --- | --- |
| XML de NF-e / NFC-e | Parser local. Valor, data, emitente, itens e forma de pagamento. |
| Linha digitável / código de barras | Parser local (boleto bancário e contas de consumo/tributos), com conferência de todos os dígitos verificadores. |
| PDF com texto | Texto extraído e interpretado pela IA; linha digitável e chave da NF-e encontradas são conferidas. |
| Foto, print, PDF escaneado | IA com visão via [OpenRouter](https://openrouter.ai). |
| Mensagem | IA via OpenRouter. |

Para gravar tudo corretamente:

- **Valores em centavos inteiros**, sem erro de arredondamento.
- **Dados verificáveis prevalecem sobre a IA**: valor e vencimento de boleto
  vêm da linha digitável validada; divergências ficam anotadas.
- **Sem duplicidade**: o mesmo arquivo, a mesma NF-e (mesmo vinda do XML e do
  DANFE) e o mesmo boleto não entram duas vezes.
- **Baixa automática**: o comprovante de pagamento de um boleto pendente
  passa o boleto para pago, com a data e o valor pagos.
- **Fila de revisão**: leituras incertas, valores divergentes ou lançamentos
  parecidos com outro (mesmo valor, ±3 dias) ficam marcados para conferência.
- **Cada usuário só vê os próprios dados** (regras do Firestore e do Storage).

## Estrutura

| Pasta | Conteúdo |
| --- | --- |
| `mobile/` | App Flutter (Android, iOS e web). |
| `functions/` | Cloud Functions em Python (`ingest_file`, `ingest_text`). |
| `financas_core/` | Leitura de NF-e, boleto, IA e regras de deduplicação, compartilhados. |
| `firestore.rules`, `storage.rules` | Regras de segurança. |
| `app/` | Versão alternativa para rodar num computador (FastAPI + SQLite + página web). |

## Colocando no ar

### 1. Criar o projeto no Firebase

No [console do Firebase](https://console.firebase.google.com):

1. Crie um projeto.
2. Mude para o plano **Blaze** (obrigatório para Cloud Functions; o uso
   pessoal costuma ficar dentro da cota gratuita).
3. **Authentication** → Método de login → ative **E-mail/senha**.
4. **Firestore Database** → criar banco em modo de produção, região
   `southamerica-east1 (São Paulo)`.
5. **Storage** → começar, mesma região.

### 2. Instalar as ferramentas no computador

- [Node.js](https://nodejs.org) e o Firebase CLI: `npm install -g firebase-tools`
- [Python 3.12](https://www.python.org)
- [Flutter](https://docs.flutter.dev/get-started/install)
- FlutterFire CLI: `dart pub global activate flutterfire_cli`

### 3. Publicar o backend

```bash
firebase login
firebase use --add                      # escolha o projeto criado
firebase functions:secrets:set OPENROUTER_API_KEY   # cole sua chave da OpenRouter

cd functions
python3.12 -m venv venv
venv/bin/pip install -r requirements.txt
cd ..
firebase deploy                         # funções, regras e índices
```

O `firebase deploy` copia `financas_core/` para dentro de `functions/`
automaticamente (`scripts/sync-core.sh`). O modelo de IA pode ser trocado com
o parâmetro `OPENROUTER_MODEL` (padrão `google/gemini-2.5-flash`), que o CLI
pergunta no primeiro deploy.

### 4. Instalar o app no celular

```bash
cd mobile
flutterfire configure --platforms=android,ios   # gera lib/firebase_options.dart
flutter run --release                            # com o celular conectado por USB
```

- **Android**: ative a depuração USB no celular, ou gere o instalador com
  `flutter build apk --release` e copie `build/app/outputs/flutter-apk/app-release.apk`
  para o aparelho.
- **iPhone**: precisa de um Mac com Xcode. Antes do primeiro build, em
  `mobile/ios/Podfile` descomente e ajuste a linha `platform :ios, '15.0'`.

Abra o app, crie sua conta e, em **Ajustes**, cadastre seu CPF/CNPJ (é assim
que o app sabe se uma nota é uma venda sua ou uma compra).

## Testando sem publicar

**Modo demonstração** (dados de exemplo, sem Firebase):

```bash
cd mobile && flutter run --dart-define=DEMO=true
```

**Emuladores do Firebase** (tudo local, sem custo):

```bash
scripts/sync-core.sh
echo "OPENROUTER_API_KEY=off" > functions/.secret.local   # ou sua chave real
firebase emulators:start --project demo-financas
# em outro terminal:
cd mobile && flutter run --dart-define=USE_EMULATORS=true --dart-define=EMULATOR_HOST=10.0.2.2
```

`EMULATOR_HOST=10.0.2.2` é o endereço do computador visto pelo emulador
Android; num celular de verdade use o IP do computador na rede.

## Testes

```bash
# núcleo e servidor local
pip install -r requirements-dev.txt && pytest

# backend Firebase, contra os emuladores
scripts/sync-core.sh
firebase emulators:exec --only firestore --project demo-financas \
  "functions/venv/bin/pytest functions/tests -q"
firebase emulators:exec --project demo-financas "python3 scripts/e2e_emulators.py"

# app
cd mobile && flutter analyze && flutter test
```

## Versão para computador (opcional)

A pasta `app/` tem uma versão que roda num computador, sem Firebase, com
página web própria e banco SQLite:

```bash
pip install -r requirements.txt
cp .env.example .env   # OPENROUTER_API_KEY e OWNER_DOCUMENTS
uvicorn app.main:app --reload    # http://localhost:8000
```

## Limitações conhecidas

- Uma compra pode aparecer em mais de um documento (NF-e + fatura do cartão,
  NF-e + boleto). Quando valores e datas batem, o segundo vai para revisão
  como possível duplicidade, mas a decisão é sua.
- A linha digitável não informa o beneficiário; boletos lançados só pela linha
  ficam para revisão até você conferir a descrição.
- Para enviar um comprovante direto do app do banco ("Compartilhar"), por
  enquanto salve o print e escolha em **Prints e fotos**.
