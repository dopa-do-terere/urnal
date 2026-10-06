"""Regras de gravação comuns a todos os backends.

Cada backend (SQLite local, Firestore) implementa `Store`; esta camada
decide o que fazer com cada rascunho:

- mesmo `external_id` (código de barras / chave de NF-e) já gravado:
  se o rascunho é um pagamento e o existente está pendente, dá baixa;
  senão é duplicidade e nada é gravado;
- mesmo valor e tipo em datas próximas: grava, mas manda para revisão;
- caso contrário: grava.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol

from financas_core.categories import resolve_category
from financas_core.extraction import Draft, Extraction

# Janela para considerar duas movimentações de mesmo valor como suspeitas.
SIMILAR_WINDOW_DAYS = 3


class StoredTx(Protocol):
    id: Any
    kind: str
    status: str
    description: str
    occurred_on: Any  # date ou "AAAA-MM-DD"


class AlreadyExists(Exception):
    """Levantada por `Store.create` quando outro processo gravou o mesmo
    `external_id` ao mesmo tempo."""

    def __init__(self, existing: StoredTx):
        super().__init__("movimentação já existe")
        self.existing = existing


class Store(Protocol):
    def find_by_external_id(self, external_id: str) -> list[StoredTx]: ...

    def find_similar(self, draft: Draft, window_days: int) -> StoredTx | None: ...

    def mark_paid(self, existing: StoredTx, draft: Draft, note: str) -> StoredTx: ...

    def create(self, draft: Draft, category: str) -> StoredTx: ...


@dataclass
class PersistResult:
    created: list = field(default_factory=list)
    updated: list = field(default_factory=list)
    duplicates: list = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _fmt_date(value: Any) -> str:
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, str) and len(value) >= 10:
        return f"{value[8:10]}/{value[5:7]}/{value[0:4]}"
    return str(value)


def persist_drafts(store: Store, extraction: Extraction) -> PersistResult:
    result = PersistResult(warnings=list(extraction.warnings))

    for draft in extraction.drafts:
        if draft.external_id:
            existing = store.find_by_external_id(draft.external_id)
            pending = [t for t in existing if t.status == "pending" and t.kind == draft.kind]
            if draft.status == "paid" and pending:
                note = f"Baixa automática pelo comprovante de {_fmt_date(draft.occurred_on)}."
                result.updated.append(store.mark_paid(pending[0], draft, note))
                continue
            if existing:
                result.duplicates.append(existing[0])
                continue

        similar = store.find_similar(draft, SIMILAR_WINDOW_DAYS)
        if similar is not None:
            draft.needs_review = True
            draft.notes.append(
                f'Possível duplicidade com "{similar.description}" de {_fmt_date(similar.occurred_on)}.'
            )
        category = resolve_category(draft.kind, draft.category, draft.description, draft.counterparty)
        try:
            result.created.append(store.create(draft, category))
        except AlreadyExists as exc:
            result.duplicates.append(exc.existing)

    if not extraction.drafts:
        result.warnings.append("Nenhuma movimentação encontrada.")
    if result.duplicates and not (result.created or result.updated):
        result.warnings.append("Documento já registrado anteriormente.")
    return result
