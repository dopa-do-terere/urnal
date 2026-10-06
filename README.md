# Assistente de Finanças

Registra suas movimentações financeiras a partir do que você mandar: XML de
NF-e/NFC-e, PDFs (DANFE, boletos, faturas, extratos), prints e fotos de
comprovantes e cupons, linhas digitáveis ou mensagens como
_"gastei 45,90 no ifood ontem no nubank"_.

## Como funciona

| Entrada | Como é lida |
| --- | --- |
| XML de NF-e / NFC-e | Parser local. Valor, data, emitente, itens e forma de pagamento. |
| Linha digitável / código de barras | Parser local (boleto bancário e contas de consumo/tributos), com conferência de todos os dígitos verificadores. |
| PDF com texto | Texto extraído localmente e interpretado pela IA; linha digitável e chave da NF-e encontradas no texto são conferidas. |
| PDF escaneado, prints, fotos | IA com visão via [OpenRouter](https://openrouter.ai). |
| Mensagem de texto | IA via OpenRouter. |

Para gravar tudo corretamente:

- **Valores em centavos inteiros** — sem erro de arredondamento.
- **Dados verificáveis prevalecem sobre a IA**: se a IA lê um boleto, o valor
  e o vencimento vêm da linha digitável validada; a divergência fica anotada.
- **Sem duplicidade**: o mesmo arquivo (hash), a mesma NF-e (chave de acesso,
  mesmo vindo de XML e de DANFE) e o mesmo boleto (código de barras) não são
  lançados de novo.
- **Baixa automática**: ao enviar o comprovante de pagamento de um boleto
  pendente, o boleto passa para pago com a data e o valor efetivamente pagos.
- **Fila de revisão**: extrações com baixa confiança, valores divergentes ou
  lançamentos parecidos com um já existente (mesmo valor, ±3 dias) ficam
  marcados como "revisar".
- Os arquivos originais ficam guardados em `data/uploads/` e podem ser
  baixados pela API.

## Rodando

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # preencha OPENROUTER_API_KEY e OWNER_DOCUMENTS
uvicorn app.main:app --reload
```

Abra http://localhost:8000. A documentação interativa da API fica em
http://localhost:8000/docs.

Sem `OPENROUTER_API_KEY` o sistema funciona só com XML de NF-e, linhas
digitáveis e lançamentos manuais. O modelo é escolhido em `OPENROUTER_MODEL`
(precisa aceitar imagens; padrão `google/gemini-2.5-flash`).

## API

| Método | Rota | Descrição |
| --- | --- | --- |
| POST | `/api/ingest/files` | Envia um ou mais arquivos (`multipart`, campo `files`). |
| POST | `/api/ingest/text` | `{"text": "..."}` — mensagem ou linha digitável. |
| GET | `/api/transactions` | Filtros: `month=AAAA-MM`, `start`, `end`, `kind`, `status`, `category`, `needs_review`, `q`. |
| POST | `/api/transactions` | Lançamento manual. `amount` aceita `"1.234,56"`. |
| PATCH / DELETE | `/api/transactions/{id}` | Editar / excluir. |
| POST | `/api/transactions/{id}/confirm` | Tira da fila de revisão. |
| POST | `/api/transactions/{id}/pay` | Marca como pago (`paid_on`, `amount` opcionais). |
| GET | `/api/summary?month=AAAA-MM` | Receitas, despesas, saldo, pendências, por categoria, vencidos e a vencer. |
| GET | `/api/export.csv?month=AAAA-MM` | Exporta para planilha (separador `;`). |
| GET | `/api/documents/{id}/file` | Baixa o arquivo original. |

## Testes

```bash
pip install -r requirements-dev.txt
pytest
```

## Limitações conhecidas

- Uma compra pode aparecer em mais de um documento (NF-e + fatura do cartão,
  NF-e + boleto). Quando os valores e datas batem, o segundo lançamento vai
  para revisão como possível duplicidade, mas a decisão é sua.
- A linha digitável não informa o beneficiário; boletos lançados só pela linha
  ficam para revisão até você conferir a descrição.
- Fotos HEIC (iPhone) precisam ser enviadas como JPG/PNG.
