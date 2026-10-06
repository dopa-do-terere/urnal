from datetime import date

from app.parsers.boleto import _BASE_NEW, _bancario_barcode_to_line, _mod10, _mod11_arrecadacao, _mod11_bancario


def make_bancario_line(amount_cents: int, due: date, bank: str = "341", free: str = "1" * 25) -> str:
    factor = (due - _BASE_NEW).days + 1000
    body = f"{bank}9{factor:04d}{amount_cents:010d}{free}"
    dv = _mod11_bancario(body)
    barcode = body[:4] + str(dv) + body[4:]
    return _bancario_barcode_to_line(barcode)


def make_arrecadacao_line(amount_cents: int, segment: str = "3", ident: str = "6") -> str:
    body = f"8{segment}{ident}{amount_cents:011d}{'0123' * 8}"[:43]
    module = _mod10 if ident in "67" else _mod11_arrecadacao
    barcode = body[:3] + str(module(body)) + body[3:]
    return "".join(b + str(module(b)) for b in (barcode[i : i + 11] for i in range(0, 44, 11)))


def make_access_key(cnpj: str = "11222333000181", number: int = 1234, model: str = "55") -> str:
    body = f"35" f"2610" f"{cnpj}" f"{model}" f"001" f"{number:09d}" f"1" f"{number:08d}"
    total, weight = 0, 2
    for digit in reversed(body):
        total += int(digit) * weight
        weight = 2 if weight == 9 else weight + 1
    rest = total % 11
    return body + str(0 if rest in (0, 1) else 11 - rest)


def make_nfe_xml(
    key: str,
    total: str = "150.75",
    issuer_doc: str = "11222333000181",
    recipient_doc: str = "12345678909",
    issuer_name: str = "SUPERMERCADO BOM PRECO LTDA",
) -> bytes:
    issuer_tag = "CNPJ" if len(issuer_doc) == 14 else "CPF"
    recipient_tag = "CNPJ" if len(recipient_doc) == 14 else "CPF"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
  <NFe>
    <infNFe Id="NFe{key}" versao="4.00">
      <ide><nNF>1234</nNF><serie>1</serie><dhEmi>2026-10-01T10:15:00-03:00</dhEmi></ide>
      <emit><{issuer_tag}>{issuer_doc}</{issuer_tag}><xNome>{issuer_name}</xNome></emit>
      <dest><{recipient_tag}>{recipient_doc}</{recipient_tag}><xNome>FULANO DE TAL</xNome></dest>
      <det nItem="1"><prod><xProd>ARROZ 5KG</xProd><qCom>2.0000</qCom><vUnCom>25.50</vUnCom><vProd>51.00</vProd></prod></det>
      <det nItem="2"><prod><xProd>CAFE 500G</xProd><qCom>1.0000</qCom><vUnCom>99.75</vUnCom><vProd>99.75</vProd></prod></det>
      <total><ICMSTot><vNF>{total}</vNF></ICMSTot></total>
      <pag><detPag><tPag>17</tPag><vPag>{total}</vPag></detPag></pag>
    </infNFe>
  </NFe>
</nfeProc>""".encode()
