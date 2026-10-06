"""Gravação no Firestore, em users/{uid}/transactions e users/{uid}/documents.

Datas são guardadas como texto "AAAA-MM-DD": ordenam corretamente, não
sofrem com fuso horário e permitem consultas por intervalo de mês.
"""

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from google.api_core.exceptions import AlreadyExists as FirestoreAlreadyExists
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from financas_core.extraction import Draft, Extraction, Extractor, IngestError, extract_file, extract_text
from financas_core.persistence import AlreadyExists, PersistResult, persist_drafts
from financas_core.text import only_digits

MAX_UPLOAD_BYTES = 20 * 1024 * 1024


@dataclass
class FsTx:
    id: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def kind(self) -> str:
        return self.data.get("kind", "expense")

    @property
    def status(self) -> str:
        return self.data.get("status", "paid")

    @property
    def description(self) -> str:
        return self.data.get("description", "")

    @property
    def occurred_on(self) -> str:
        return self.data.get("occurred_on", "")

    def to_json(self) -> dict[str, Any]:
        keys = ("kind", "status", "amount_cents", "description", "category", "occurred_on", "due_date", "needs_review")
        return {"id": self.id, **{k: self.data.get(k) for k in keys}}


def _snap(snapshot) -> FsTx:
    return FsTx(snapshot.id, snapshot.to_dict() or {})


def _iso(value: date | None) -> str | None:
    return value.isoformat() if value else None


def transaction_data(draft: Draft, category: str, document_id: str | None) -> dict[str, Any]:
    return {
        "kind": draft.kind,
        "status": draft.status,
        "amount_cents": draft.amount_cents,
        "description": draft.description,
        "category": category,
        "counterparty": draft.counterparty,
        "counterparty_doc": draft.counterparty_doc,
        "payment_method": draft.payment_method,
        "account": draft.account,
        "occurred_on": draft.occurred_on.isoformat(),
        "due_date": _iso(draft.due_date),
        "external_id": draft.external_id,
        "source": draft.source,
        "needs_review": draft.needs_review,
        "notes": "\n".join(draft.notes) or None,
        "document_id": document_id,
        "payment_document_id": None,
        "items": draft.items,
        "created_at": firestore.SERVER_TIMESTAMP,
        "updated_at": firestore.SERVER_TIMESTAMP,
    }


class FirestoreStore:
    """Implementa financas_core.persistence.Store."""

    def __init__(self, user_ref, document: dict[str, Any] | None = None):
        self.transactions = user_ref.collection("transactions")
        self.documents = user_ref.collection("documents")
        self._document = document  # {"id": sha256, ...campos}
        self.document_id: str | None = None

    def _ensure_document(self) -> str | None:
        if self._document is not None and self.document_id is None:
            fields = {k: v for k, v in self._document.items() if k != "id"}
            self.documents.document(self._document["id"]).set({**fields, "created_at": firestore.SERVER_TIMESTAMP})
            self.document_id = self._document["id"]
        return self.document_id

    def find_by_external_id(self, external_id: str) -> list[FsTx]:
        query = self.transactions.where(filter=FieldFilter("external_id", "==", external_id))
        return [_snap(s) for s in query.stream()]

    def find_similar(self, draft: Draft, window_days: int) -> FsTx | None:
        if not draft.amount_cents:
            return None
        start = (draft.occurred_on - timedelta(days=window_days)).isoformat()
        end = (draft.occurred_on + timedelta(days=window_days)).isoformat()
        query = self.transactions.where(filter=FieldFilter("amount_cents", "==", draft.amount_cents)).where(
            filter=FieldFilter("kind", "==", draft.kind)
        )
        for snapshot in query.stream():
            data = snapshot.to_dict() or {}
            dates = (data.get("occurred_on"), data.get("due_date"))
            if any(d and start <= d <= end for d in dates):
                return FsTx(snapshot.id, data)
        return None

    def mark_paid(self, existing: FsTx, draft: Draft, note: str) -> FsTx:
        notes = existing.data.get("notes")
        update = {
            "status": "paid",
            "occurred_on": draft.occurred_on.isoformat(),
            "amount_cents": draft.amount_cents or existing.data.get("amount_cents", 0),
            "payment_method": draft.payment_method or existing.data.get("payment_method"),
            "account": draft.account or existing.data.get("account"),
            "payment_document_id": self._ensure_document(),
            "notes": f"{notes}\n{note}" if notes else note,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }
        self.transactions.document(existing.id).update(update)
        return FsTx(existing.id, {**existing.data, **update})

    def create(self, draft: Draft, category: str) -> FsTx:
        data = transaction_data(draft, category, self._ensure_document())
        if draft.external_id:
            # Id determinístico: dois envios simultâneos do mesmo boleto ou
            # da mesma nota não geram dois lançamentos.
            ref = self.transactions.document(f"x{draft.external_id}")
            try:
                ref.create(data)
            except FirestoreAlreadyExists as exc:
                raise AlreadyExists(_snap(ref.get())) from exc
        else:
            ref = self.transactions.document()
            ref.set(data)
        return FsTx(ref.id, data)


def owner_documents(user_ref) -> frozenset[str]:
    snapshot = user_ref.get()
    docs = (snapshot.to_dict() or {}).get("owner_documents") if snapshot.exists else None
    return frozenset(d for d in (only_digits(str(x)) for x in docs or []) if d)


def _response(result: PersistResult, document: dict | None) -> dict[str, Any]:
    return {
        "document": document,
        "created": [t.to_json() for t in result.created],
        "updated": [t.to_json() for t in result.updated],
        "duplicates": [t.to_json() for t in result.duplicates],
        "warnings": result.warnings,
    }


def ingest_uploaded_file(
    user_ref,
    *,
    path: str,
    filename: str,
    content: bytes,
    mime: str | None,
    ai: Extractor | None,
    delete_upload: Callable[[], None],
) -> dict[str, Any]:
    """Processa um arquivo já enviado ao Storage. O arquivo é apagado se
    for repetido ou se não gerar nenhum lançamento."""
    if len(content) > MAX_UPLOAD_BYTES:
        delete_upload()
        raise IngestError("Arquivo maior que 20 MB.")
    sha = hashlib.sha256(content).hexdigest()
    existing_doc = user_ref.collection("documents").document(sha).get()
    if existing_doc.exists:
        delete_upload()
        transactions = user_ref.collection("transactions")
        related = [
            _snap(s)
            for f in ("document_id", "payment_document_id")
            for s in transactions.where(filter=FieldFilter(f, "==", sha)).stream()
        ]
        result = PersistResult(duplicates=related, warnings=["Este arquivo já foi enviado antes."])
        return _response(result, {"id": sha, "filename": (existing_doc.to_dict() or {}).get("filename")})

    try:
        extraction: Extraction = extract_file(filename, content, mime, ai, owner_documents(user_ref))
    except IngestError:
        delete_upload()
        raise

    store = FirestoreStore(
        user_ref,
        {
            "id": sha,
            "filename": filename[:255],
            "mime_type": mime,
            "kind": extraction.doc_kind[:30],
            "storage_path": path,
            "size": len(content),
            "extracted": extraction.extracted or None,
        },
    )
    result = persist_drafts(store, extraction)
    if store.document_id is None:
        delete_upload()
        return _response(result, None)
    return _response(result, {"id": sha, "filename": filename})


def ingest_message(user_ref, text: str, ai: Extractor | None) -> dict[str, Any]:
    extraction = extract_text(text, ai, owner_documents(user_ref))
    return _response(persist_drafts(FirestoreStore(user_ref), extraction), None)
