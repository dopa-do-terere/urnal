"""Ingestão no backend local (SQLite via SQLAlchemy)."""

import hashlib
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Document, Transaction, TransactionItem
from financas_core.ai import AIConfig, OpenRouterClient
from financas_core.extraction import Draft, Extraction, Extractor, IngestError, extract_file, extract_text
from financas_core.persistence import persist_drafts

__all__ = ["IngestError", "IngestOutcome", "get_ai", "ingest_file", "ingest_text"]


def get_ai() -> Extractor | None:
    if not settings.openrouter_api_key:
        return None
    return OpenRouterClient(
        AIConfig(
            api_key=settings.openrouter_api_key,
            model=settings.openrouter_model,
            base_url=settings.openrouter_base_url,
        )
    )


@dataclass
class IngestOutcome:
    document: Document | None = None
    created: list[Transaction] = field(default_factory=list)
    updated: list[Transaction] = field(default_factory=list)
    duplicates: list[Transaction] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _append_note(tx: Transaction, note: str) -> None:
    tx.notes = f"{tx.notes}\n{note}" if tx.notes else note


class SqlStore:
    """Implementa financas_core.persistence.Store sobre SQLAlchemy."""

    def __init__(self, db: Session, file: tuple[str, str, bytes, str | None] | None, extraction: Extraction):
        self.db = db
        self.file = file  # (sha256, nome, conteúdo, mime)
        self.extraction = extraction
        self.document: Document | None = None

    def _get_document(self) -> Document | None:
        if self.document is None and self.file is not None:
            sha, filename, content, mime = self.file
            suffix = Path(filename).suffix.lower()[:10] if filename else ""
            path = settings.upload_dir / f"{sha}{suffix}"
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_bytes(content)
            self.document = Document(
                sha256=sha,
                filename=(filename or path.name)[:255],
                mime_type=mime,
                kind=self.extraction.doc_kind[:30],
                storage_path=str(path),
                extracted=self.extraction.extracted or None,
            )
            self.db.add(self.document)
            self.db.flush()
        return self.document

    def find_by_external_id(self, external_id: str) -> list[Transaction]:
        return list(
            self.db.scalars(
                select(Transaction).where(Transaction.external_id == external_id).order_by(Transaction.id)
            )
        )

    def find_similar(self, draft: Draft, window_days: int) -> Transaction | None:
        if not draft.amount_cents:
            return None
        window = timedelta(days=window_days)
        start, end = draft.occurred_on - window, draft.occurred_on + window
        return self.db.scalars(
            select(Transaction)
            .where(
                Transaction.kind == draft.kind,
                Transaction.amount_cents == draft.amount_cents,
                or_(Transaction.occurred_on.between(start, end), Transaction.due_date.between(start, end)),
            )
            .limit(1)
        ).first()

    def mark_paid(self, existing: Transaction, draft: Draft, note: str) -> Transaction:
        existing.status = "paid"
        existing.occurred_on = draft.occurred_on
        existing.amount_cents = draft.amount_cents or existing.amount_cents
        existing.payment_method = draft.payment_method or existing.payment_method
        existing.account = draft.account or existing.account
        document = self._get_document()
        if document is not None:
            existing.payment_document_id = document.id
        _append_note(existing, note)
        return existing

    def create(self, draft: Draft, category: str) -> Transaction:
        tx = Transaction(
            kind=draft.kind,
            status=draft.status,
            amount_cents=draft.amount_cents,
            description=draft.description,
            category=category,
            counterparty=draft.counterparty,
            counterparty_doc=draft.counterparty_doc,
            payment_method=draft.payment_method,
            account=draft.account,
            occurred_on=draft.occurred_on,
            due_date=draft.due_date,
            external_id=draft.external_id,
            source=draft.source,
            needs_review=draft.needs_review,
            notes="\n".join(draft.notes) or None,
            document=self._get_document(),
        )
        tx.items = [TransactionItem(**item) for item in draft.items]
        self.db.add(tx)
        # Garante que buscas seguintes do mesmo envio enxerguem este registro.
        self.db.flush()
        return tx


def _persist(db: Session, extraction: Extraction, file=None) -> IngestOutcome:
    store = SqlStore(db, file, extraction)
    result = persist_drafts(store, extraction)
    db.commit()
    return IngestOutcome(store.document, result.created, result.updated, result.duplicates, result.warnings)


def ingest_file(db: Session, filename: str, content: bytes, mime: str | None) -> IngestOutcome:
    if not content:
        raise IngestError("Arquivo vazio.")
    if len(content) > settings.max_upload_bytes:
        raise IngestError("Arquivo maior que o limite configurado (MAX_UPLOAD_MB).")
    sha = hashlib.sha256(content).hexdigest()
    existing = db.scalar(select(Document).where(Document.sha256 == sha))
    if existing is not None:
        related = db.scalars(
            select(Transaction).where(
                or_(Transaction.document_id == existing.id, Transaction.payment_document_id == existing.id)
            )
        ).all()
        return IngestOutcome(
            document=existing, duplicates=list(related), warnings=["Este arquivo já foi enviado antes."]
        )
    extraction = extract_file(filename, content, mime, get_ai(), settings.owner_documents)
    return _persist(db, extraction, (sha, filename, content, mime))


def ingest_text(db: Session, text: str) -> IngestOutcome:
    return _persist(db, extract_text(text, get_ai(), settings.owner_documents))
