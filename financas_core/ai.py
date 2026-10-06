"""Extração de movimentações via OpenRouter (API compatível com OpenAI)."""

import base64
import json
import logging
from dataclasses import dataclass
from datetime import date

import httpx

from financas_core.categories import EXPENSE_CATEGORIES, INCOME_CATEGORIES

log = logging.getLogger(__name__)


class AIError(RuntimeError):
    pass


SYSTEM_PROMPT = """Você é um assistente de finanças pessoais no Brasil. Sua tarefa é \
extrair movimentações financeiras de documentos (NF-e, NFC-e, cupons fiscais, \
boletos, comprovantes de Pix/TED/pagamento, faturas de cartão, extratos, recibos, \
prints de aplicativos) ou de mensagens escritas pelo usuário.

Responda APENAS com um objeto JSON, sem texto fora dele, no formato:
{
  "document_type": "nfe|nfce|cupom|boleto|comprovante|fatura_cartao|extrato|recibo|mensagem|outro",
  "transactions": [
    {
      "kind": "expense|income",
      "status": "paid|pending",
      "amount": 123.45,
      "description": "descrição curta e útil",
      "category": "uma das categorias permitidas",
      "counterparty": "quem recebeu ou quem pagou",
      "counterparty_doc": "CPF/CNPJ só com dígitos ou null",
      "payment_method": "Pix|Cartão de crédito|Cartão de débito|Dinheiro|Boleto|Transferência|Débito automático|Outro|null",
      "account": "banco/conta/cartão do usuário usado, ou null",
      "occurred_on": "AAAA-MM-DD",
      "due_date": "AAAA-MM-DD ou null",
      "boleto_line": "linha digitável ou código de barras, só dígitos, ou null",
      "nfe_access_key": "chave de acesso de 44 dígitos ou null",
      "items": [{"description": "...", "quantity": 1, "unit_price": 10.0, "total": 10.0}],
      "confidence": 0.0
    }
  ],
  "notes": "ambiguidades ou o que não foi possível ler"
}

Regras:
- "amount" é sempre positivo, em reais, com ponto decimal. O sentido vem de "kind".
- Nunca invente valores, datas ou nomes. Se algo estiver ilegível, use null e explique em "notes". \
Se não houver nenhuma movimentação, devolva "transactions": [].
- Boleto ainda não pago: status "pending", "due_date" = vencimento e "occurred_on" = vencimento. \
Copie a linha digitável inteira em "boleto_line" se estiver visível.
- Comprovante de pagamento (Pix, TED, boleto pago): status "paid", "occurred_on" = data do pagamento, \
"amount" = valor efetivamente pago. Se for pagamento de boleto, copie a linha digitável em "boleto_line".
- NF-e/NFC-e/cupom: uma única movimentação com o valor total da nota e os itens em "items". \
Copie a chave de acesso (44 dígitos) em "nfe_access_key" se estiver visível.
- Fatura de cartão: uma movimentação por compra (expense, paid, payment_method "Cartão de crédito", \
account = cartão). Ignore "pagamento recebido", saldo anterior, encargos já listados como total e limites. \
Parcelas: registre só a parcela cobrada nesta fatura e indique "(parcela X/Y)" na descrição.
- Extrato: uma movimentação por lançamento; ignore linhas de saldo.
- Mensagem do usuário ("gastei 50 no mercado ontem", "recebi 3000 de salário"): interprete datas \
relativas a partir da data de hoje e preencha o que for possível.
- "confidence": sua confiança (0 a 1) de que valor, data e tipo estão corretos.
"""


def text_part(text: str) -> dict:
    return {"type": "text", "text": text}


def image_part(content: bytes, mime_type: str) -> dict:
    data = base64.b64encode(content).decode()
    return {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{data}"}}


def pdf_part(content: bytes, filename: str) -> dict:
    data = base64.b64encode(content).decode()
    return {
        "type": "file",
        "file": {"filename": filename or "documento.pdf", "file_data": f"data:application/pdf;base64,{data}"},
    }


DEFAULT_MODEL = "google/gemini-2.5-flash"
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


@dataclass(frozen=True)
class AIConfig:
    api_key: str
    model: str = DEFAULT_MODEL
    base_url: str = DEFAULT_BASE_URL
    timeout: float = 120


def _context_text(hint: str | None, owner_documents: frozenset[str]) -> str:
    owner = ", ".join(sorted(owner_documents)) or "não informados"
    lines = [
        f"Data de hoje: {date.today().isoformat()}.",
        f"CPF/CNPJ do usuário: {owner}. Se o usuário for quem recebe o dinheiro, kind = income.",
        f"Categorias de despesa permitidas: {', '.join(EXPENSE_CATEGORIES)}.",
        f"Categorias de receita permitidas: {', '.join(INCOME_CATEGORIES)}.",
    ]
    if hint:
        lines.append(hint)
    return "\n".join(lines)


def _parse_json(content: str) -> dict:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.removeprefix("json").strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise AIError("a IA não devolveu JSON")
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise AIError(f"JSON inválido devolvido pela IA: {exc}") from exc
    if not isinstance(data, dict):
        raise AIError("a IA devolveu um JSON inesperado")
    data.setdefault("transactions", [])
    return data


class OpenRouterClient:
    """Implementa o protocolo `Extractor` usado por financas_core.extraction."""

    def __init__(self, config: AIConfig):
        if not config.api_key:
            raise AIError("OPENROUTER_API_KEY não configurada")
        self.config = config

    def extract(
        self, parts: list[dict], hint: str | None = None, owner_documents: frozenset[str] = frozenset()
    ) -> dict:
        """Envia o conteúdo para o modelo e devolve o JSON extraído."""
        payload = {
            "model": self.config.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": [text_part(_context_text(hint, owner_documents)), *parts]},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "X-Title": "Assistente de Finanças",
        }
        try:
            response = httpx.post(
                f"{self.config.base_url.rstrip('/')}/chat/completions",
                json=payload,
                headers=headers,
                timeout=self.config.timeout,
            )
        except httpx.HTTPError as exc:
            raise AIError(f"falha ao chamar a OpenRouter: {exc}") from exc
        if response.status_code >= 400:
            raise AIError(f"OpenRouter respondeu {response.status_code}: {response.text[:500]}")

        try:
            message = response.json()["choices"][0]["message"]
        except (ValueError, KeyError, IndexError) as exc:
            raise AIError("resposta inesperada da OpenRouter") from exc
        content = message.get("content")
        if isinstance(content, list):  # alguns provedores devolvem partes
            content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
        if not content:
            raise AIError("a IA devolveu uma resposta vazia")
        return _parse_json(content)
