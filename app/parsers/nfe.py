"""Leitura do XML de NF-e (modelo 55) e NFC-e (modelo 65)."""

from dataclasses import dataclass, field
from datetime import date
from xml.etree.ElementTree import Element

from defusedxml import ElementTree as SafeET

from app.config import only_digits
from app.money import MoneyError, to_cents
from app.parsers import digit_windows

PAYMENT_METHODS = {
    "01": "Dinheiro",
    "02": "Cheque",
    "03": "Cartão de crédito",
    "04": "Cartão de débito",
    "05": "Crédito loja",
    "10": "Vale alimentação",
    "11": "Vale refeição",
    "12": "Vale presente",
    "13": "Vale combustível",
    "15": "Boleto",
    "16": "Depósito",
    "17": "Pix",
    "18": "Transferência",
    "19": "Programa de fidelidade",
    "90": "Sem pagamento",
    "99": "Outro",
}

_UF_CODES = {
    "11", "12", "13", "14", "15", "16", "17", "21", "22", "23", "24", "25", "26", "27",
    "28", "29", "31", "32", "33", "35", "41", "42", "43", "50", "51", "52", "53",
}


class NFeError(ValueError):
    pass


@dataclass
class NFeItem:
    description: str
    quantity: float | None
    unit_price_cents: int | None
    total_cents: int


@dataclass
class NFe:
    access_key: str
    model: str
    number: str | None
    series: str | None
    issued_on: date
    issuer_name: str | None
    issuer_doc: str | None
    recipient_name: str | None
    recipient_doc: str | None
    total_cents: int
    items: list[NFeItem] = field(default_factory=list)
    payment_methods: list[str] = field(default_factory=list)


def access_key_is_valid(key: str) -> bool:
    if len(key) != 44 or not key.isdigit():
        return False
    if key[:2] not in _UF_CODES or key[20:22] not in ("55", "65"):
        return False
    total, weight = 0, 2
    for digit in reversed(key[:43]):
        total += int(digit) * weight
        weight = 2 if weight == 9 else weight + 1
    rest = total % 11
    dv = 0 if rest in (0, 1) else 11 - rest
    return dv == int(key[43])


def find_access_key(text: str) -> str | None:
    for candidate in digit_windows(text, 44):
        if access_key_is_valid(candidate):
            return candidate
    return None


def _text(node: Element | None, path: str) -> str | None:
    if node is None:
        return None
    found = node.find(path)
    if found is None or found.text is None:
        return None
    return found.text.strip() or None


def _party(node: Element | None) -> tuple[str | None, str | None]:
    if node is None:
        return None, None
    doc = _text(node, "{*}CNPJ") or _text(node, "{*}CPF")
    return _text(node, "{*}xNome"), only_digits(doc) or None


def _cents(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return to_cents(value)
    except MoneyError:
        return None


def parse_nfe_xml(content: bytes) -> NFe:
    try:
        root = SafeET.fromstring(content)
    except Exception as exc:  # defusedxml levanta vários tipos
        raise NFeError(f"XML inválido: {exc}") from exc

    inf = root if root.tag.endswith("infNFe") else root.find(".//{*}infNFe")
    if inf is None:
        raise NFeError("XML não contém uma NF-e (infNFe não encontrado)")

    key = only_digits(inf.get("Id"))
    if not key:
        key = only_digits(_text(root, ".//{*}protNFe/{*}infProt/{*}chNFe"))
    if not access_key_is_valid(key):
        raise NFeError("chave de acesso ausente ou inválida")

    ide = inf.find("{*}ide")
    issued = _text(ide, "{*}dhEmi") or _text(ide, "{*}dEmi")
    if not issued:
        raise NFeError("data de emissão não encontrada")
    try:
        issued_on = date.fromisoformat(issued[:10])
    except ValueError as exc:
        raise NFeError(f"data de emissão inválida: {issued}") from exc

    total = _cents(_text(inf, "{*}total/{*}ICMSTot/{*}vNF"))
    if total is None:
        raise NFeError("valor total (vNF) não encontrado")

    issuer_name, issuer_doc = _party(inf.find("{*}emit"))
    recipient_name, recipient_doc = _party(inf.find("{*}dest"))
    issuer_name = _text(inf, "{*}emit/{*}xFant") or issuer_name

    items = []
    for det in inf.findall("{*}det"):
        prod = det.find("{*}prod")
        item_total = _cents(_text(prod, "{*}vProd"))
        if prod is None or item_total is None:
            continue
        qty = _text(prod, "{*}qCom")
        items.append(
            NFeItem(
                description=_text(prod, "{*}xProd") or "Item",
                quantity=float(qty) if qty else None,
                unit_price_cents=_cents(_text(prod, "{*}vUnCom")),
                total_cents=item_total,
            )
        )

    payments = []
    for det_pag in inf.findall("{*}pag/{*}detPag") + inf.findall("{*}pag"):
        code = _text(det_pag, "{*}tPag")
        if code and PAYMENT_METHODS.get(code, "Outro") not in payments:
            payments.append(PAYMENT_METHODS.get(code, "Outro"))

    return NFe(
        access_key=key,
        model=key[20:22],
        number=_text(ide, "{*}nNF"),
        series=_text(ide, "{*}serie"),
        issued_on=issued_on,
        issuer_name=issuer_name,
        issuer_doc=issuer_doc,
        recipient_name=recipient_name,
        recipient_doc=recipient_doc,
        total_cents=total,
        items=items,
        payment_methods=payments,
    )
