"""Conversão de valores monetários. Tudo é guardado em centavos (int) para
evitar erros de arredondamento de ponto flutuante."""

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

_THOUSANDS_DOTS = re.compile(r"^\d{1,3}(\.\d{3})+$")


class MoneyError(ValueError):
    pass


def to_cents(value: object) -> int:
    """Converte 123.45, "123,45", "R$ 1.234,56", "1,234.56" etc. em centavos.

    O sinal é descartado: se é entrada ou saída é definido pelo tipo da
    movimentação, não pelo valor.
    """
    if value is None or isinstance(value, bool):
        raise MoneyError("valor ausente")
    if isinstance(value, int):
        return abs(value) * 100
    if isinstance(value, float):
        dec = Decimal(repr(value))
    elif isinstance(value, Decimal):
        dec = value
    else:
        text = str(value).strip().replace("R$", "").replace(" ", "").replace(" ", "")
        text = text.lstrip("+-")
        if not text:
            raise MoneyError("valor vazio")
        if "," in text and "." in text:
            if text.rfind(",") > text.rfind("."):
                text = text.replace(".", "").replace(",", ".")
            else:
                text = text.replace(",", "")
        elif "," in text:
            text = text.replace(",", ".")
        elif _THOUSANDS_DOTS.match(text):
            text = text.replace(".", "")
        try:
            dec = Decimal(text)
        except InvalidOperation as exc:
            raise MoneyError(f"valor inválido: {value!r}") from exc
    if not dec.is_finite():
        raise MoneyError(f"valor inválido: {value!r}")
    return int((abs(dec) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def cents_to_decimal(cents: int) -> Decimal:
    return (Decimal(cents) / 100).quantize(Decimal("0.01"))
