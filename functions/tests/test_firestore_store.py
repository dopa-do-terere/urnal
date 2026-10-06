"""Testes contra o emulador do Firestore.

    cd functions && ../scripts/sync-core.sh
    firebase emulators:exec --only firestore --project demo-financas "venv/bin/pytest tests -q"
"""

import importlib.util
import os
import sys
import uuid
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "functions"), str(ROOT)]

from google.cloud import firestore  # noqa: E402

from financas_core.extraction import IngestError  # noqa: E402
from firestore_store import ingest_message, ingest_uploaded_file  # noqa: E402
_spec = importlib.util.spec_from_file_location("shared_helpers", ROOT / "tests" / "helpers.py")
helpers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(helpers)
make_access_key, make_bancario_line, make_nfe_xml = helpers.make_access_key, helpers.make_bancario_line, helpers.make_nfe_xml

pytestmark = pytest.mark.skipif(
    not os.environ.get("FIRESTORE_EMULATOR_HOST"), reason="precisa do emulador do Firestore"
)


@pytest.fixture()
def user():
    db = firestore.Client(project=os.environ.get("GCLOUD_PROJECT", "demo-financas"))
    ref = db.collection("users").document(f"test-{uuid.uuid4().hex}")
    ref.set({"owner_documents": ["123.456.789-09"]})
    return ref


class FakeAI:
    def __init__(self, response):
        self.response = response

    def extract(self, parts, hint=None, owner_documents=frozenset()):
        self.owner_documents = owner_documents
        return self.response


def upload(user, content, name="arquivo", ai=None):
    deleted = []
    result = ingest_uploaded_file(
        user,
        path=f"users/{user.id}/uploads/{name}",
        filename=name,
        content=content,
        mime=None,
        ai=ai,
        delete_upload=lambda: deleted.append(True),
    )
    return result, bool(deleted)


def all_transactions(user):
    return [s.to_dict() | {"id": s.id} for s in user.collection("transactions").stream()]


def test_nfe_is_saved_once_and_document_kept(user):
    key = make_access_key()
    result, deleted = upload(user, make_nfe_xml(key), "nota.xml")
    assert not deleted
    [tx] = result["created"]
    assert tx["amount_cents"] == 15075 and tx["occurred_on"] == "2026-10-01" and tx["category"] == "Mercado"
    stored = all_transactions(user)
    assert len(stored) == 1 and stored[0]["external_id"] == key and len(stored[0]["items"]) == 2
    assert user.collection("documents").document(result["document"]["id"]).get().exists

    # mesmo arquivo: apagado do Storage e marcado como repetido
    again, deleted = upload(user, make_nfe_xml(key), "nota.xml")
    assert deleted and again["created"] == [] and again["duplicates"][0]["id"] == tx["id"]

    # mesma nota com conteúdo diferente: duplicidade pela chave de acesso
    other, deleted = upload(user, make_nfe_xml(key).replace(b"FULANO", b"BELTRANO"), "nota2.xml")
    assert deleted and other["created"] == [] and len(all_transactions(user)) == 1


def test_owner_document_from_profile_makes_income(user):
    key = make_access_key(number=55)
    result, _ = upload(user, make_nfe_xml(key, issuer_doc="12345678909", recipient_doc="11222333000181"))
    assert result["created"][0]["kind"] == "income"


def test_boleto_then_receipt_marks_paid(user):
    line = make_bancario_line(25990, date(2026, 11, 10))
    created = ingest_message(user, line, ai=None)["created"][0]
    assert created["status"] == "pending" and created["due_date"] == "2026-11-10"

    ai = FakeAI({
        "document_type": "comprovante",
        "transactions": [{
            "kind": "expense", "status": "paid", "amount": 259.90, "description": "Pagamento",
            "occurred_on": "2026-11-08", "boleto_line": line, "confidence": 0.95,
        }],
    })
    result, deleted = upload(user, b"\x89PNG\r\n\x1a\nfake", "comprovante.png", ai=ai)
    assert not deleted and result["created"] == []
    assert result["updated"][0]["id"] == created["id"]
    stored = user.collection("transactions").document(created["id"]).get().to_dict()
    assert stored["status"] == "paid" and stored["occurred_on"] == "2026-11-08"
    assert stored["payment_document_id"] == result["document"]["id"]
    assert "Baixa automática" in stored["notes"]
    assert ai.owner_documents == frozenset({"12345678909"})


def test_similar_amount_goes_to_review(user):
    ai = FakeAI({"transactions": [{"kind": "expense", "amount": "45,90", "description": "iFood",
                                   "occurred_on": "2026-10-05", "confidence": 0.99}]})
    first = ingest_message(user, "gastei 45,90 no ifood", ai)["created"][0]
    assert first["needs_review"] is False
    second = ingest_message(user, "ifood 45,90", ai)["created"][0]
    assert second["needs_review"] is True


def test_unreadable_upload_is_deleted(user):
    with pytest.raises(IngestError):
        upload(user, b"\x89PNG\r\n\x1a\nfake", "print.png", ai=None)
    assert all_transactions(user) == []
