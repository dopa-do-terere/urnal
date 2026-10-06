from datetime import date

import pytest

from app.config import settings
from app.services import ingest
from tests.helpers import make_access_key, make_bancario_line, make_nfe_xml


@pytest.fixture()
def fake_ai(monkeypatch):
    """Substitui a chamada à OpenRouter por uma resposta fixa."""
    calls = []
    response = {"document_type": "mensagem", "transactions": []}

    class FakeAI:
        def extract(self, parts, hint=None, owner_documents=frozenset()):
            calls.append(parts)
            return response

    monkeypatch.setattr(ingest, "get_ai", lambda: FakeAI())
    return response, calls


def upload(client, name, content, mime="application/octet-stream"):
    res = client.post("/api/ingest/files", files=[("files", (name, content, mime))])
    assert res.status_code == 200
    return res.json()[0]


def test_nfe_xml_is_saved_once(client):
    key = make_access_key()
    result = upload(client, "nota.xml", make_nfe_xml(key), "text/xml")
    assert result["error"] is None
    [tx] = result["created"]
    assert tx["kind"] == "expense"
    assert tx["amount_cents"] == 15075
    assert tx["amount"] == "150.75"
    assert tx["category"] == "Mercado"
    assert tx["external_id"] == key
    assert tx["needs_review"] is False
    assert len(tx["items"]) == 2

    # mesmo arquivo de novo
    again = upload(client, "nota.xml", make_nfe_xml(key), "text/xml")
    assert again["created"] == [] and len(again["duplicates"]) == 1

    # mesma nota em outro arquivo (conteúdo diferente, mesma chave)
    other = upload(client, "nota2.xml", make_nfe_xml(key).replace(b"FULANO", b"BELTRANO"), "text/xml")
    assert other["created"] == [] and other["duplicates"][0]["id"] == tx["id"]

    assert len(client.get("/api/transactions").json()) == 1


def test_nfe_issued_by_owner_is_income(client):
    key = make_access_key(cnpj="00012345678909", number=99)
    result = upload(client, "venda.xml", make_nfe_xml(key, issuer_doc="12345678909", recipient_doc="11222333000181"))
    assert result["created"][0]["kind"] == "income"


def test_boleto_line_then_payment_receipt(client, fake_ai):
    due = date(2026, 11, 10)
    line = make_bancario_line(25990, due)

    res = client.post("/api/ingest/text", json={"text": line})
    assert res.status_code == 200
    [boleto_tx] = res.json()["created"]
    assert boleto_tx["status"] == "pending"
    assert boleto_tx["amount_cents"] == 25990
    assert boleto_tx["due_date"] == due.isoformat()

    # comprovante (imagem) lido pela IA com a mesma linha digitável: dá baixa
    response, _ = fake_ai
    response.update(
        document_type="comprovante",
        transactions=[{
            "kind": "expense", "status": "paid", "amount": 259.90, "description": "Pagamento de boleto",
            "occurred_on": "2026-11-08", "payment_method": "Boleto", "boleto_line": line, "confidence": 0.95,
        }],
    )
    result = upload(client, "comprovante.png", b"\x89PNG\r\n\x1a\nfake", "image/png")
    assert result["created"] == []
    [paid] = result["updated"]
    assert paid["id"] == boleto_tx["id"]
    assert paid["status"] == "paid"
    assert paid["occurred_on"] == "2026-11-08"
    assert paid["payment_document_id"] == result["document"]["id"]


def test_ai_values_are_checked_against_boleto_line(client, fake_ai):
    line = make_bancario_line(10000, date(2026, 12, 5))
    response, _ = fake_ai
    response.update(
        document_type="boleto",
        transactions=[{
            "kind": "expense", "status": "pending", "amount": 1000.00, "description": "Escola",
            "category": "Educação", "occurred_on": "2026-12-05", "due_date": "2026-12-15",
            "boleto_line": line, "confidence": 0.99,
        }],
    )
    [tx] = upload(client, "boleto.jpg", b"\xff\xd8\xff\xe0fake", "image/jpeg")["created"]
    assert tx["amount_cents"] == 10000
    assert tx["due_date"] == "2026-12-05"
    assert tx["category"] == "Educação"
    assert tx["needs_review"] is True  # valor divergente fica registrado para revisão


def test_text_message_and_review_flow(client, fake_ai):
    response, calls = fake_ai
    response.update(
        transactions=[{
            "kind": "expense", "amount": "45,90", "description": "iFood", "category": "alimentacao",
            "occurred_on": "2026-10-05", "payment_method": "Cartão de crédito", "account": "Nubank",
            "confidence": 0.7,
        }],
    )
    res = client.post("/api/ingest/text", json={"text": "gastei 45,90 no ifood ontem no nubank"})
    [tx] = res.json()["created"]
    assert calls and tx["amount_cents"] == 4590
    assert tx["category"] == "Alimentação"
    assert tx["needs_review"] is True

    assert client.post(f"/api/transactions/{tx['id']}/confirm").json()["needs_review"] is False

    # mesmo gasto lançado de novo é marcado como possível duplicidade
    dup = client.post("/api/ingest/text", json={"text": "45,90 ifood"}).json()["created"][0]
    assert "Possível duplicidade" in dup["notes"]


def test_without_ai_images_are_rejected_with_clear_message(client):
    result = upload(client, "print.png", b"\x89PNG\r\n\x1a\nfake", "image/png")
    assert "OPENROUTER_API_KEY" in result["error"]
    assert client.get("/api/transactions").json() == []


def test_manual_crud_summary_and_export(client):
    base = {"occurred_on": "2026-10-03"}
    client.post("/api/transactions", json={**base, "kind": "income", "amount": "5.000,00", "description": "Salário"})
    client.post("/api/transactions", json={**base, "amount": 120.5, "description": "Farmácia"})
    pending = client.post(
        "/api/transactions",
        json={"amount": "300", "description": "Aluguel", "status": "pending", "due_date": "2026-10-10"},
    ).json()
    assert pending["category"] == "Moradia"
    assert pending["occurred_on"] == "2026-10-10"

    summary = client.get("/api/summary?month=2026-10").json()
    assert summary["income_cents"] == 500000
    assert summary["expense_cents"] == 12050
    assert summary["balance_cents"] == 487950
    assert summary["pending_expense_cents"] == 30000

    paid = client.post(f"/api/transactions/{pending['id']}/pay", json={"paid_on": "2026-10-09"}).json()
    assert paid["status"] == "paid" and paid["occurred_on"] == "2026-10-09"

    edited = client.patch(f"/api/transactions/{paid['id']}", json={"amount": "310,00"}).json()
    assert edited["amount_cents"] == 31000

    assert client.patch(f"/api/transactions/{paid['id']}", json={"amount": "abc"}).status_code == 422

    csv_text = client.get("/api/export.csv?month=2026-10").text
    assert "Farmácia" in csv_text and "-120,50" in csv_text

    assert client.delete(f"/api/transactions/{paid['id']}").status_code == 204
    assert len(client.get("/api/transactions?month=2026-10").json()) == 2


def test_uploaded_file_is_stored(client):
    key = make_access_key(number=777)
    result = upload(client, "nota.xml", make_nfe_xml(key), "text/xml")
    doc_id = result["document"]["id"]
    res = client.get(f"/api/documents/{doc_id}/file")
    assert res.status_code == 200 and key.encode() in res.content
    assert any(settings.upload_dir.iterdir())
