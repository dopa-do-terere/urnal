from datetime import date, datetime, timezone

from sqlalchemy import JSON, CheckConstraint, Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Document(Base):
    """Arquivo enviado (XML, PDF, imagem). Guardado em disco pelo hash."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    sha256: Mapped[str] = mapped_column(String(64), unique=True)
    filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str | None] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(30))
    storage_path: Mapped[str] = mapped_column(String(500))
    extracted: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(default=_now)

    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="document", foreign_keys="Transaction.document_id"
    )


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("amount_cents >= 0", name="ck_amount_non_negative"),
        CheckConstraint("kind IN ('expense', 'income')", name="ck_kind"),
        CheckConstraint("status IN ('paid', 'pending')", name="ck_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(10), default="paid")
    amount_cents: Mapped[int]
    description: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(60), index=True)
    counterparty: Mapped[str | None] = mapped_column(String(255))
    counterparty_doc: Mapped[str | None] = mapped_column(String(14))
    payment_method: Mapped[str | None] = mapped_column(String(40))
    account: Mapped[str | None] = mapped_column(String(100))
    occurred_on: Mapped[date] = mapped_column(Date, index=True)
    due_date: Mapped[date | None] = mapped_column(Date, index=True)
    # Código de barras do boleto ou chave de acesso da NF-e: identifica o
    # mesmo documento mesmo que chegue por arquivos diferentes.
    external_id: Mapped[str | None] = mapped_column(String(48), index=True)
    source: Mapped[str] = mapped_column(String(20))
    needs_review: Mapped[bool] = mapped_column(default=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    payment_document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(default=_now)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now)

    document: Mapped[Document | None] = relationship(
        back_populates="transactions", foreign_keys=[document_id]
    )
    items: Mapped[list["TransactionItem"]] = relationship(
        back_populates="transaction", cascade="all, delete-orphan", lazy="selectin"
    )


class TransactionItem(Base):
    __tablename__ = "transaction_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id", ondelete="CASCADE"))
    description: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[float | None]
    unit_price_cents: Mapped[int | None]
    total_cents: Mapped[int]

    transaction: Mapped[Transaction] = relationship(back_populates="items")
