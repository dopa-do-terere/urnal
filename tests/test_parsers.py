from datetime import date

import pytest

from financas_core.money import MoneyError, to_cents
from financas_core.parsers.boleto import BoletoError, due_date_from_factor, find_boleto, parse_boleto
from financas_core.parsers.nfe import NFeError, access_key_is_valid, find_access_key, parse_nfe_xml
from tests.helpers import make_access_key, make_arrecadacao_line, make_bancario_line, make_nfe_xml


@pytest.mark.parametrize(
    "value, cents",
    [
        ("123,45", 12345),
        ("R$ 1.234,56", 123456),
        ("1,234.56", 123456),
        ("1.234", 123400),
        ("10.5", 1050),
        (10.1, 1010),
        (0.1 + 0.2, 30),
        ("-45,90", 4590),
        (7, 700),
    ],
)
def test_to_cents(value, cents):
    assert to_cents(value) == cents


@pytest.mark.parametrize("value", [None, "", "abc", "R$", True])
def test_to_cents_invalid(value):
    with pytest.raises(MoneyError):
        to_cents(value)


def test_boleto_banco_do_brasil_official_example():
    boleto = parse_boleto("00190.50095 40144.816069 06809.350314 3 37370000000100", reference=date(2007, 12, 1))
    assert boleto.type == "bancario"
    assert boleto.bank_name == "Banco do Brasil"
    assert boleto.amount_cents == 100
    assert boleto.due_date == date(2007, 12, 31)
    assert boleto.barcode == "00193373700000001000500940144816060680935031"


def test_boleto_roundtrip_new_factor_cycle():
    line = make_bancario_line(98765, date(2026, 11, 10))
    boleto = parse_boleto(line)
    assert boleto.amount_cents == 98765
    assert boleto.due_date == date(2026, 11, 10)
    assert boleto.bank_name == "Itaú"
    assert parse_boleto(boleto.barcode).digitable_line == line


def test_boleto_rejects_wrong_digit():
    line = make_bancario_line(98765, date(2026, 11, 10))
    tampered = line[:12] + str((int(line[12]) + 1) % 10) + line[13:]
    with pytest.raises(BoletoError):
        parse_boleto(tampered)


def test_factor_transition():
    assert due_date_from_factor(9999, date(2025, 2, 1)) == date(2025, 2, 21)
    assert due_date_from_factor(1000, date(2025, 3, 1)) == date(2025, 2, 22)
    assert due_date_from_factor(0) is None


@pytest.mark.parametrize("ident", ["6", "8"])
def test_arrecadacao(ident):
    line = make_arrecadacao_line(18990, segment="3", ident=ident)
    boleto = parse_boleto(line)
    assert boleto.type == "arrecadacao"
    assert boleto.amount_cents == 18990
    assert boleto.segment == "Energia elétrica e gás"


def test_find_boleto_in_text():
    line = make_bancario_line(5000, date(2026, 10, 20))
    formatted = f"{line[:5]}.{line[5:10]} {line[10:15]}.{line[15:21]} {line[21:26]}.{line[26:32]} {line[32]} {line[33:]}"
    text = f"Beneficiário: ACME LTDA\nCNPJ 11.222.333/0001-81\n{formatted}\nVencimento 20/10/2026"
    boleto = find_boleto(text)
    assert boleto is not None and boleto.amount_cents == 5000


def test_access_key():
    key = make_access_key()
    assert access_key_is_valid(key)
    assert not access_key_is_valid(key[:-1] + str((int(key[-1]) + 1) % 10))
    spaced = " ".join(key[i : i + 4] for i in range(0, 44, 4))
    assert find_access_key(f"CHAVE DE ACESSO\n{spaced}\n") == key


def test_parse_nfe_xml():
    key = make_access_key()
    nfe = parse_nfe_xml(make_nfe_xml(key))
    assert nfe.access_key == key
    assert nfe.total_cents == 15075
    assert nfe.issued_on == date(2026, 10, 1)
    assert nfe.issuer_doc == "11222333000181"
    assert nfe.payment_methods == ["Pix"]
    assert [i.total_cents for i in nfe.items] == [5100, 9975]


def test_parse_nfe_rejects_other_xml():
    with pytest.raises(NFeError):
        parse_nfe_xml(b"<root><a>1</a></root>")
    with pytest.raises(NFeError):
        parse_nfe_xml(b"<!DOCTYPE x [<!ENTITY a 'b'>]><x>&a;</x>")
