import csv
import io
import logging
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.ai import openrouter
from app.config import settings
from app.db import get_db, init_db
from app.models import Document, Transaction
from app.money import MoneyError, cents_to_decimal, to_cents
from app.schemas import (
    CategoryTotal,
    DocumentOut,
    IngestResult,
    PayRequest,
    Summary,
    TextIngest,
    TransactionCreate,
    TransactionOut,
    TransactionUpdate,
)
from app.services.categories import EXPENSE_CATEGORIES, INCOME_CATEGORIES, resolve_category
from app.services.ingest import IngestError, IngestOutcome, ingest_file, ingest_text

logging.basicConfig(level=logging.INFO)
STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Assistente de Finanças", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

DB = Annotated[Session, Depends(get_db)]


def _cents_or_422(value) -> int:
    try:
        return to_cents(value)
    except MoneyError as exc:
        raise HTTPException(422, str(exc)) from exc


def _month_range(month: str | None) -> tuple[date, date, str]:
    if month:
        try:
            year, mon = (int(p) for p in month.split("-"))
            start = date(year, mon, 1)
        except ValueError as exc:
            raise HTTPException(422, "month deve estar no formato AAAA-MM") from exc
    else:
        start = date.today().replace(day=1)
    end = (start + timedelta(days=32)).replace(day=1)
    return start, end, f"{start:%Y-%m}"


def _get_tx(db: Session, tx_id: int) -> Transaction:
    tx = db.get(Transaction, tx_id)
    if tx is None:
        raise HTTPException(404, "movimentação não encontrada")
    return tx


def _result(outcome: IngestOutcome, filename: str | None = None) -> IngestResult:
    return IngestResult(
        filename=filename,
        document=DocumentOut.model_validate(outcome.document) if outcome.document else None,
        created=[TransactionOut.model_validate(t) for t in outcome.created],
        updated=[TransactionOut.model_validate(t) for t in outcome.updated],
        duplicates=[TransactionOut.model_validate(t) for t in outcome.duplicates],
        warnings=outcome.warnings,
    )


# --- páginas e metadados ----------------------------------------------------


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "ai_configured": openrouter.is_configured(),
        "model": settings.openrouter_model if openrouter.is_configured() else None,
    }


@app.get("/api/categories")
def categories():
    return {"expense": EXPENSE_CATEGORIES, "income": INCOME_CATEGORIES}


# --- ingestão ----------------------------------------------------------------


@app.post("/api/ingest/files", response_model=list[IngestResult])
async def ingest_files(db: DB, files: Annotated[list[UploadFile], File()]):
    results = []
    for upload in files:
        content = await upload.read(settings.max_upload_bytes + 1)
        name = upload.filename or "arquivo"
        try:
            outcome = ingest_file(db, name, content, upload.content_type)
        except IngestError as exc:
            db.rollback()
            results.append(IngestResult(filename=name, error=str(exc)))
            continue
        results.append(_result(outcome, name))
    return results


@app.post("/api/ingest/text", response_model=IngestResult)
def ingest_message(db: DB, body: TextIngest):
    try:
        outcome = ingest_text(db, body.text)
    except IngestError as exc:
        raise HTTPException(422, str(exc)) from exc
    return _result(outcome)


# --- movimentações -----------------------------------------------------------


@app.get("/api/transactions", response_model=list[TransactionOut])
def list_transactions(
    db: DB,
    month: str | None = None,
    start: date | None = None,
    end: date | None = None,
    kind: str | None = None,
    status: str | None = None,
    category: str | None = None,
    needs_review: bool | None = None,
    q: str | None = None,
    limit: int = Query(200, le=1000),
    offset: int = 0,
):
    stmt = select(Transaction)
    if month:
        m_start, m_end, _ = _month_range(month)
        stmt = stmt.where(Transaction.occurred_on >= m_start, Transaction.occurred_on < m_end)
    if start:
        stmt = stmt.where(Transaction.occurred_on >= start)
    if end:
        stmt = stmt.where(Transaction.occurred_on <= end)
    if kind:
        stmt = stmt.where(Transaction.kind == kind)
    if status:
        stmt = stmt.where(Transaction.status == status)
    if category:
        stmt = stmt.where(Transaction.category == category)
    if needs_review is not None:
        stmt = stmt.where(Transaction.needs_review == needs_review)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                Transaction.description.ilike(like),
                Transaction.counterparty.ilike(like),
                Transaction.notes.ilike(like),
            )
        )
    stmt = stmt.order_by(Transaction.occurred_on.desc(), Transaction.id.desc()).limit(limit).offset(offset)
    return db.scalars(stmt).all()


@app.post("/api/transactions", response_model=TransactionOut, status_code=201)
def create_transaction(db: DB, body: TransactionCreate):
    tx = Transaction(
        kind=body.kind,
        status=body.status,
        amount_cents=_cents_or_422(body.amount),
        description=body.description.strip(),
        category=resolve_category(body.kind, body.category, body.description, body.counterparty),
        counterparty=body.counterparty,
        payment_method=body.payment_method,
        account=body.account,
        occurred_on=body.occurred_on or body.due_date or date.today(),
        due_date=body.due_date,
        notes=body.notes,
        source="manual",
    )
    db.add(tx)
    db.commit()
    return tx


@app.get("/api/transactions/{tx_id}", response_model=TransactionOut)
def get_transaction(db: DB, tx_id: int):
    return _get_tx(db, tx_id)


@app.patch("/api/transactions/{tx_id}", response_model=TransactionOut)
def update_transaction(db: DB, tx_id: int, body: TransactionUpdate):
    tx = _get_tx(db, tx_id)
    data = body.model_dump(exclude_unset=True)
    if "amount" in data:
        if data["amount"] is None:
            raise HTTPException(422, "amount não pode ser nulo")
        tx.amount_cents = _cents_or_422(data.pop("amount"))
    if "category" in data:
        kind = data.get("kind") or tx.kind
        tx.category = resolve_category(kind, data.pop("category"), tx.description, tx.counterparty)
    for field, value in data.items():
        if field in ("kind", "status", "description", "occurred_on", "needs_review") and value is None:
            raise HTTPException(422, f"{field} não pode ser nulo")
        setattr(tx, field, value)
    db.commit()
    return tx


@app.post("/api/transactions/{tx_id}/confirm", response_model=TransactionOut)
def confirm_transaction(db: DB, tx_id: int):
    tx = _get_tx(db, tx_id)
    tx.needs_review = False
    db.commit()
    return tx


@app.post("/api/transactions/{tx_id}/pay", response_model=TransactionOut)
def pay_transaction(db: DB, tx_id: int, body: PayRequest | None = None):
    tx = _get_tx(db, tx_id)
    body = body or PayRequest()
    tx.status = "paid"
    tx.occurred_on = body.paid_on or date.today()
    if body.amount is not None:
        tx.amount_cents = _cents_or_422(body.amount)
    tx.payment_method = body.payment_method or tx.payment_method
    tx.account = body.account or tx.account
    db.commit()
    return tx


@app.delete("/api/transactions/{tx_id}", status_code=204)
def delete_transaction(db: DB, tx_id: int):
    db.delete(_get_tx(db, tx_id))
    db.commit()


# --- resumo e exportação -----------------------------------------------------


@app.get("/api/summary", response_model=Summary)
def summary(db: DB, month: str | None = None):
    start, end, label = _month_range(month)
    in_month = (Transaction.occurred_on >= start, Transaction.occurred_on < end)

    totals = {
        (kind, status): total
        for kind, status, total in db.execute(
            select(Transaction.kind, Transaction.status, func.sum(Transaction.amount_cents))
            .where(*in_month)
            .group_by(Transaction.kind, Transaction.status)
        )
    }
    by_category = [
        CategoryTotal(kind=kind, category=category, total_cents=total)
        for kind, category, total in db.execute(
            select(Transaction.kind, Transaction.category, func.sum(Transaction.amount_cents))
            .where(*in_month, Transaction.status == "paid")
            .group_by(Transaction.kind, Transaction.category)
            .order_by(func.sum(Transaction.amount_cents).desc())
        )
    ]
    today = date.today()
    pending_by_due = (
        select(Transaction)
        .where(Transaction.status == "pending")
        .order_by(func.coalesce(Transaction.due_date, Transaction.occurred_on))
    )
    due = func.coalesce(Transaction.due_date, Transaction.occurred_on)
    overdue = db.scalars(pending_by_due.where(due < today)).all()
    upcoming = db.scalars(pending_by_due.where(due >= today, due <= today + timedelta(days=15))).all()
    income = totals.get(("income", "paid"), 0)
    expense = totals.get(("expense", "paid"), 0)
    return Summary(
        month=label,
        income_cents=income,
        expense_cents=expense,
        balance_cents=income - expense,
        pending_income_cents=totals.get(("income", "pending"), 0),
        pending_expense_cents=totals.get(("expense", "pending"), 0),
        by_category=by_category,
        to_review=db.scalar(select(func.count()).where(Transaction.needs_review.is_(True))) or 0,
        overdue=overdue,
        upcoming=upcoming,
    )


@app.get("/api/export.csv")
def export_csv(db: DB, month: str | None = None):
    stmt = select(Transaction).order_by(Transaction.occurred_on, Transaction.id)
    filename = "movimentacoes.csv"
    if month:
        start, end, label = _month_range(month)
        stmt = stmt.where(Transaction.occurred_on >= start, Transaction.occurred_on < end)
        filename = f"movimentacoes-{label}.csv"
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(
        ["id", "data", "tipo", "status", "valor", "descricao", "categoria", "contraparte",
         "forma_pagamento", "conta", "vencimento", "origem", "revisar"]
    )
    for tx in db.scalars(stmt):
        signed = cents_to_decimal(tx.amount_cents if tx.kind == "income" else -tx.amount_cents)
        writer.writerow(
            [tx.id, tx.occurred_on.isoformat(), "receita" if tx.kind == "income" else "despesa",
             "pago" if tx.status == "paid" else "pendente", str(signed).replace(".", ","),
             tx.description, tx.category, tx.counterparty or "", tx.payment_method or "",
             tx.account or "", tx.due_date.isoformat() if tx.due_date else "", tx.source,
             "sim" if tx.needs_review else "nao"]
        )
    return StreamingResponse(
        iter(["﻿" + buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --- documentos --------------------------------------------------------------


@app.get("/api/documents/{doc_id}", response_model=DocumentOut)
def get_document(db: DB, doc_id: int):
    doc = db.get(Document, doc_id)
    if doc is None:
        raise HTTPException(404, "documento não encontrado")
    return doc


@app.get("/api/documents/{doc_id}/file")
def download_document(db: DB, doc_id: int):
    doc = db.get(Document, doc_id)
    if doc is None or not Path(doc.storage_path).exists():
        raise HTTPException(404, "documento não encontrado")
    return FileResponse(doc.storage_path, media_type=doc.mime_type, filename=doc.filename)
