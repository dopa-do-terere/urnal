from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.money import cents_to_decimal

Kind = Literal["expense", "income"]
Status = Literal["paid", "pending"]
# Aceita 123.45, "123,45", "R$ 1.234,56"; convertido com app.money.to_cents.
MoneyInput = Decimal | float | int | str


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    description: str
    quantity: float | None
    unit_price_cents: int | None
    total_cents: int


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: Kind
    status: Status
    amount_cents: int
    description: str
    category: str
    counterparty: str | None
    counterparty_doc: str | None
    payment_method: str | None
    account: str | None
    occurred_on: date
    due_date: date | None
    external_id: str | None
    source: str
    needs_review: bool
    notes: str | None
    document_id: int | None
    payment_document_id: int | None
    items: list[ItemOut]
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def amount(self) -> Decimal:
        return cents_to_decimal(self.amount_cents)


class TransactionCreate(BaseModel):
    kind: Kind = "expense"
    status: Status = "paid"
    amount: MoneyInput
    description: str = Field(min_length=1, max_length=255)
    category: str | None = None
    counterparty: str | None = Field(default=None, max_length=255)
    payment_method: str | None = Field(default=None, max_length=40)
    account: str | None = Field(default=None, max_length=100)
    occurred_on: date | None = None
    due_date: date | None = None
    notes: str | None = None


class TransactionUpdate(BaseModel):
    kind: Kind | None = None
    status: Status | None = None
    amount: MoneyInput | None = None
    description: str | None = Field(default=None, min_length=1, max_length=255)
    category: str | None = None
    counterparty: str | None = Field(default=None, max_length=255)
    payment_method: str | None = Field(default=None, max_length=40)
    account: str | None = Field(default=None, max_length=100)
    occurred_on: date | None = None
    due_date: date | None = None
    notes: str | None = None
    needs_review: bool | None = None


class PayRequest(BaseModel):
    paid_on: date | None = None
    amount: MoneyInput | None = None
    payment_method: str | None = Field(default=None, max_length=40)
    account: str | None = Field(default=None, max_length=100)


class TextIngest(BaseModel):
    text: str = Field(min_length=1, max_length=60_000)


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    mime_type: str | None
    kind: str
    created_at: datetime


class IngestResult(BaseModel):
    filename: str | None = None
    error: str | None = None
    document: DocumentOut | None = None
    created: list[TransactionOut] = []
    updated: list[TransactionOut] = []
    duplicates: list[TransactionOut] = []
    warnings: list[str] = []


class CategoryTotal(BaseModel):
    kind: Kind
    category: str
    total_cents: int


class Summary(BaseModel):
    month: str
    income_cents: int
    expense_cents: int
    balance_cents: int
    pending_income_cents: int
    pending_expense_cents: int
    by_category: list[CategoryTotal]
    to_review: int
    overdue: list[TransactionOut]
    upcoming: list[TransactionOut]
