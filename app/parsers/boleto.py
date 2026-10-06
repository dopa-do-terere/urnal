"""Leitura de boletos pela linha digitável ou código de barras (padrão FEBRABAN).

- Boleto bancário: linha de 47 dígitos / código de barras de 44 começando
  pelo código do banco.
- Arrecadação (água, luz, telefone, tributos): linha de 48 dígitos /
  código de barras de 44 começando com 8.

Todos os dígitos verificadores são conferidos, então um valor só é aceito
se a linha estiver íntegra.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from app.parsers import digit_windows

BANKS = {
    "001": "Banco do Brasil",
    "033": "Santander",
    "041": "Banrisul",
    "070": "BRB",
    "077": "Banco Inter",
    "104": "Caixa Econômica Federal",
    "208": "BTG Pactual",
    "212": "Banco Original",
    "237": "Bradesco",
    "260": "Nubank",
    "290": "PagSeguro",
    "323": "Mercado Pago",
    "336": "C6 Bank",
    "341": "Itaú",
    "380": "PicPay",
    "422": "Safra",
    "748": "Sicredi",
    "756": "Sicoob",
}

SEGMENTS = {
    "1": "Prefeituras",
    "2": "Saneamento",
    "3": "Energia elétrica e gás",
    "4": "Telecomunicações",
    "5": "Órgãos governamentais",
    "6": "Carnês e assemelhados",
    "7": "Multas de trânsito",
    "9": "Uso exclusivo do banco",
}

# Fator de vencimento: dias desde 07/10/1997. Ao chegar em 9999
# (21/02/2025) o fator recomeçou em 1000 a partir de 22/02/2025.
_BASE_OLD = date(1997, 10, 7)
_BASE_NEW = date(2025, 2, 22)


class BoletoError(ValueError):
    pass


@dataclass(frozen=True)
class Boleto:
    type: str  # "bancario" | "arrecadacao"
    barcode: str
    digitable_line: str
    amount_cents: int | None
    due_date: date | None
    bank_code: str | None = None
    bank_name: str | None = None
    segment: str | None = None


def _mod10(number: str) -> int:
    total, weight = 0, 2
    for digit in reversed(number):
        product = int(digit) * weight
        total += product // 10 + product % 10
        weight = 1 if weight == 2 else 2
    return (10 - total % 10) % 10


def _weighted_sum_2_to_9(number: str) -> int:
    total, weight = 0, 2
    for digit in reversed(number):
        total += int(digit) * weight
        weight = 2 if weight == 9 else weight + 1
    return total


def _mod11_bancario(number: str) -> int:
    dv = 11 - _weighted_sum_2_to_9(number) % 11
    return 1 if dv in (0, 10, 11) else dv


def _mod11_arrecadacao(number: str) -> int:
    rest = _weighted_sum_2_to_9(number) % 11
    return 0 if rest in (0, 1) else 11 - rest


def due_date_from_factor(factor: int, reference: date | None = None) -> date | None:
    if factor == 0:
        return None
    reference = reference or date.today()
    candidates = [_BASE_OLD + timedelta(days=factor)]
    if factor >= 1000:
        candidates.append(_BASE_NEW + timedelta(days=factor - 1000))
    return min(candidates, key=lambda d: abs((d - reference).days))


# --- boleto bancário -------------------------------------------------------


def _bancario_line_to_barcode(line: str) -> str:
    return line[0:4] + line[32] + line[33:47] + line[4:9] + line[10:20] + line[21:31]


def _bancario_barcode_to_line(barcode: str) -> str:
    f1 = barcode[0:4] + barcode[19:24]
    f2 = barcode[24:34]
    f3 = barcode[34:44]
    return (
        f1 + str(_mod10(f1)) + f2 + str(_mod10(f2)) + f3 + str(_mod10(f3))
        + barcode[4] + barcode[5:19]
    )


def _bancario_from_barcode(barcode: str, reference: date | None) -> Boleto:
    if _mod11_bancario(barcode[:4] + barcode[5:]) != int(barcode[4]):
        raise BoletoError("dígito verificador geral do boleto inválido")
    amount = int(barcode[9:19])
    bank = barcode[:3]
    return Boleto(
        type="bancario",
        barcode=barcode,
        digitable_line=_bancario_barcode_to_line(barcode),
        amount_cents=amount or None,
        due_date=due_date_from_factor(int(barcode[5:9]), reference),
        bank_code=bank,
        bank_name=BANKS.get(bank),
    )


def _parse_bancario_line(line: str, reference: date | None) -> Boleto:
    for start, end in ((0, 9), (10, 20), (21, 31)):
        if _mod10(line[start:end]) != int(line[end]):
            raise BoletoError("dígito verificador de campo da linha digitável inválido")
    return _bancario_from_barcode(_bancario_line_to_barcode(line), reference)


# --- arrecadação (concessionárias e tributos) ------------------------------


def _arrecadacao_module(barcode: str):
    ident = barcode[2]
    if ident in "67":
        return _mod10
    if ident in "89":
        return _mod11_arrecadacao
    raise BoletoError("identificador de valor de arrecadação inválido")


def _arrecadacao_from_barcode(barcode: str) -> Boleto:
    module = _arrecadacao_module(barcode)
    if module(barcode[:3] + barcode[4:]) != int(barcode[3]):
        raise BoletoError("dígito verificador geral da conta inválido")
    blocks = [barcode[i : i + 11] for i in range(0, 44, 11)]
    line = "".join(b + str(module(b)) for b in blocks)
    # 6 e 8 indicam valor efetivo; 7 e 9 indicam valor de referência.
    amount = int(barcode[4:15]) if barcode[2] in "68" else 0
    return Boleto(
        type="arrecadacao",
        barcode=barcode,
        digitable_line=line,
        amount_cents=amount or None,
        due_date=None,
        segment=SEGMENTS.get(barcode[1]),
    )


def _parse_arrecadacao_line(line: str) -> Boleto:
    blocks = [line[i : i + 12] for i in range(0, 48, 12)]
    barcode = "".join(b[:11] for b in blocks)
    module = _arrecadacao_module(barcode)
    for block in blocks:
        if module(block[:11]) != int(block[11]):
            raise BoletoError("dígito verificador de bloco da linha digitável inválido")
    return _arrecadacao_from_barcode(barcode)


# --- API pública -----------------------------------------------------------


def parse_boleto(code: str, reference: date | None = None) -> Boleto:
    """Interpreta linha digitável (47/48 dígitos) ou código de barras (44)."""
    digits = "".join(c for c in code if c.isdigit())
    if len(digits) == 47:
        return _parse_bancario_line(digits, reference)
    if len(digits) == 48:
        if digits[0] != "8":
            raise BoletoError("linha de arrecadação deve começar com 8")
        return _parse_arrecadacao_line(digits)
    if len(digits) == 44:
        if digits[0] == "8":
            return _arrecadacao_from_barcode(digits)
        return _bancario_from_barcode(digits, reference)
    raise BoletoError(f"esperado 44, 47 ou 48 dígitos, recebido {len(digits)}")


def find_boleto(text: str, reference: date | None = None) -> Boleto | None:
    """Procura a primeira linha digitável válida num texto (ex.: PDF).

    Códigos de barras de 44 dígitos não são buscados em texto livre porque
    se confundem com chaves de acesso de NF-e.
    """
    for length in (47, 48):
        for candidate in digit_windows(text, length):
            if length == 48 and candidate[0] != "8":
                continue
            try:
                return parse_boleto(candidate, reference)
            except BoletoError:
                continue
    return None
