"""Transforma arquivos e mensagens em movimentações gravadas no banco.

Fluxo: identificar o tipo do conteúdo -> extrair rascunhos (parsers locais
e/ou IA) -> conferir dados verificáveis (linha digitável, chave da NF-e) ->
deduplicar / dar baixa em boletos pendentes -> gravar.
"""

import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.ai import openrouter
from app.config import only_digits, settings
from app.models import Document, Transaction, TransactionItem
from app.money import MoneyError, to_cents
from app.parsers.boleto import Boleto, BoletoError, find_boleto, parse_boleto
from app.parsers.nfe import NFe, NFeError, access_key_is_valid, find_access_key, parse_nfe_xml
from app.parsers.pdf import extract_pdf_text
from app.services.categories import guess_category, resolve_category

log = logging.getLogger(__name__)

# Abaixo disso a extração da IA vai para a fila de revisão.
MIN_CONFIDENCE = 0.85
# Janela para considerar duas movimentações de mesmo valor como suspeitas.
SIMILAR_WINDOW_DAYS = 3
MAX_TEXT_CHARS = 60_000


class IngestError(ValueError):
    pass


@dataclass
class Draft:
    kind: str
    amount_cents: int
    description: str
    occurred_on: date
    source: str
    status: str = "paid"
    category: str | None = None
    counterparty: str | None = None
    counterparty_doc: str | None = None
    payment_method: str | None = None
    account: str | None = None
    due_date: date | None = None
    external_id: str | None = None
    needs_review: bool = False
    notes: list[str] = field(default_factory=list)
    items: list[dict] = field(default_factory=list)


@dataclass
class Extraction:
    doc_kind: str
    drafts: list[Draft]
    extracted: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


@dataclass
class IngestOutcome:
    document: Document | None = None
    created: list[Transaction] = field(default_factory=list)
    updated: list[Transaction] = field(default_factory=list)
    duplicates: list[Transaction] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# --- rascunhos a partir dos parsers locais ---------------------------------


def draft_from_nfe(nfe: NFe) -> Draft:
    is_income = bool(nfe.issuer_doc) and nfe.issuer_doc in settings.owner_documents
    if is_income:
        counterparty, counterparty_doc = nfe.recipient_name, nfe.recipient_doc
    else:
        counterparty, counterparty_doc = nfe.issuer_name, nfe.issuer_doc
    kind = "income" if is_income else "expense"
    label = "NFC-e" if nfe.model == "65" else "NF-e"
    number = f" {nfe.number}" if nfe.number else ""
    item_names = " ".join(i.description for i in nfe.items[:10])
    return Draft(
        kind=kind,
        amount_cents=nfe.total_cents,
        description=f"{label}{number} - {counterparty or 'sem nome'}"[:255],
        occurred_on=nfe.issued_on,
        source="nfe_xml",
        category=guess_category(kind, counterparty, item_names),
        counterparty=counterparty,
        counterparty_doc=counterparty_doc,
        payment_method=", ".join(nfe.payment_methods)[:40] or None,
        external_id=nfe.access_key,
        items=[
            {
                "description": i.description,
                "quantity": i.quantity,
                "unit_price_cents": i.unit_price_cents,
                "total_cents": i.total_cents,
            }
            for i in nfe.items
        ],
    )


def _boleto_category(boleto: Boleto) -> str:
    if boleto.type == "arrecadacao":
        segment_code = boleto.barcode[1]
        if segment_code in "234":
            return "Contas de consumo"
        if segment_code in "157":
            return "Impostos e taxas"
    return "Outros"


def draft_from_boleto(boleto: Boleto) -> Draft:
    if boleto.type == "arrecadacao":
        description = f"Conta - {boleto.segment or 'arrecadação'}"
    else:
        description = f"Boleto {boleto.bank_name or boleto.bank_code}"
    notes = ["Beneficiário não identificado pela linha digitável; confira a descrição."]
    if not boleto.amount_cents:
        notes.append("Boleto sem valor fixo na linha digitável; informe o valor.")
    return Draft(
        kind="expense",
        status="pending",
        amount_cents=boleto.amount_cents or 0,
        description=description,
        occurred_on=boleto.due_date or date.today(),
        due_date=boleto.due_date,
        source="boleto",
        category=_boleto_category(boleto),
        payment_method="Boleto",
        external_id=boleto.barcode,
        needs_review=True,
        notes=notes,
    )


def apply_boleto(drafts: list[Draft], boleto: Boleto) -> None:
    """Usa os dados conferidos da linha digitável no rascunho correspondente
    (ou cria um, se a IA não trouxe nada)."""
    if any(d.external_id == boleto.barcode for d in drafts):
        return
    target = next((d for d in drafts if d.kind == "expense" and not d.external_id), None)
    if target is None:
        drafts.append(draft_from_boleto(boleto))
        return
    target.external_id = boleto.barcode
    target.payment_method = target.payment_method or "Boleto"
    if target.status == "pending":
        _trust_boleto_values(target, boleto)


def _trust_boleto_values(draft: Draft, boleto: Boleto) -> None:
    if boleto.amount_cents and draft.amount_cents != boleto.amount_cents:
        draft.notes.append(
            f"Valor ajustado pela linha digitável (lido: {draft.amount_cents / 100:.2f})."
        )
        draft.amount_cents = boleto.amount_cents
    if boleto.due_date:
        draft.due_date = boleto.due_date
        draft.occurred_on = boleto.due_date


# --- rascunhos a partir da IA ----------------------------------------------


def _parse_date(value: object) -> date | None:
    if not value or not isinstance(value, str):
        return None
    value = value.strip()
    try:
        if re.fullmatch(r"\d{2}/\d{2}/\d{4}", value):
            day, month, year = value.split("/")
            parsed = date(int(year), int(month), int(day))
        else:
            parsed = date.fromisoformat(value[:10])
    except ValueError:
        return None
    if not date(2000, 1, 1) <= parsed <= date.today() + timedelta(days=5 * 365):
        return None
    return parsed


def _clean(value: object, limit: int) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in ("null", "none"):
        return None
    return text[:limit]


def _items_from_ai(raw_items: object) -> list[dict]:
    items = []
    for raw in raw_items if isinstance(raw_items, list) else []:
        if not isinstance(raw, dict):
            continue
        try:
            total = to_cents(raw.get("total"))
        except MoneyError:
            continue
        try:
            unit = to_cents(raw.get("unit_price"))
        except MoneyError:
            unit = None
        try:
            quantity = float(raw["quantity"]) if raw.get("quantity") is not None else None
        except (TypeError, ValueError):
            quantity = None
        items.append(
            {
                "description": _clean(raw.get("description"), 255) or "Item",
                "quantity": quantity,
                "unit_price_cents": unit,
                "total_cents": total,
            }
        )
    return items


def drafts_from_ai(data: dict, source: str = "ai") -> tuple[list[Draft], list[str]]:
    doc_type = str(data.get("document_type") or "outro")
    warnings: list[str] = []
    if data.get("notes"):
        warnings.append(f"IA: {data['notes']}")
    drafts: list[Draft] = []
    raw_list = data.get("transactions")
    for index, raw in enumerate(raw_list if isinstance(raw_list, list) else [], start=1):
        if not isinstance(raw, dict):
            continue
        try:
            amount = to_cents(raw.get("amount"))
        except MoneyError:
            warnings.append(f"Movimentação {index} ignorada: valor ilegível.")
            continue

        kind = raw.get("kind") if raw.get("kind") in ("expense", "income") else "expense"
        status = raw.get("status") if raw.get("status") in ("paid", "pending") else (
            "pending" if doc_type == "boleto" else "paid"
        )
        due_date = _parse_date(raw.get("due_date"))
        occurred_on = _parse_date(raw.get("occurred_on")) or due_date
        notes: list[str] = []
        if occurred_on is None:
            occurred_on = date.today()
            notes.append("Data não identificada; usada a data de hoje.")

        counterparty = _clean(raw.get("counterparty"), 255)
        description = _clean(raw.get("description"), 255) or counterparty or "Movimentação"
        try:
            confidence = float(raw.get("confidence"))
        except (TypeError, ValueError):
            confidence = 0.0

        draft = Draft(
            kind=kind,
            status=status,
            amount_cents=amount,
            description=description,
            occurred_on=occurred_on,
            due_date=due_date,
            source=source,
            category=_clean(raw.get("category"), 60),
            counterparty=counterparty,
            counterparty_doc=only_digits(_clean(raw.get("counterparty_doc"), 30))[:14] or None,
            payment_method=_clean(raw.get("payment_method"), 40),
            account=_clean(raw.get("account"), 100),
            notes=notes,
            items=_items_from_ai(raw.get("items")),
        )

        line = only_digits(_clean(raw.get("boleto_line"), 80))
        key = only_digits(_clean(raw.get("nfe_access_key"), 80))
        if line:
            try:
                boleto = parse_boleto(line)
            except BoletoError:
                draft.notes.append("Linha digitável lida pela IA não confere; revise.")
            else:
                draft.external_id = boleto.barcode
                if draft.status == "pending":
                    _trust_boleto_values(draft, boleto)
        elif key:
            if access_key_is_valid(key):
                draft.external_id = key
            else:
                draft.notes.append("Chave de acesso lida pela IA não confere; revise.")

        draft.needs_review = confidence < MIN_CONFIDENCE or amount == 0 or bool(draft.notes)
        drafts.append(draft)
    return drafts, warnings


# --- identificação do conteúdo ---------------------------------------------


def _detect(filename: str, content: bytes, mime: str | None) -> tuple[str, str | None]:
    """Devolve (tipo, mime) com tipo em pdf, image, xml ou text."""
    if content.startswith(b"%PDF"):
        return "pdf", "application/pdf"
    if content.startswith(b"\x89PNG"):
        return "image", "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image", "image/jpeg"
    if content.startswith(b"GIF8"):
        return "image", "image/gif"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image", "image/webp"
    if content[4:12] in (b"ftypheic", b"ftypheix", b"ftypmif1"):
        raise IngestError("Fotos HEIC não são suportadas; envie como JPG ou PNG.")
    head = content[:200].lstrip(b"\xef\xbb\xbf \t\r\n")
    if filename.lower().endswith(".xml") or head.startswith(b"<"):
        return "xml", "application/xml"
    try:
        content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise IngestError(f"Tipo de arquivo não suportado ({mime or 'desconhecido'}).") from exc
    return "text", "text/plain"


def _require_ai(what: str) -> None:
    if not openrouter.is_configured():
        raise IngestError(
            f"Para ler {what} é preciso configurar OPENROUTER_API_KEY. "
            "Sem IA só são lidos XML de NF-e e linhas digitáveis de boleto."
        )


def _from_ai(parts: list[dict], hint: str | None = None) -> Extraction:
    try:
        data = openrouter.extract(parts, hint)
    except openrouter.AIError as exc:
        raise IngestError(f"Falha na leitura pela IA: {exc}") from exc
    drafts, warnings = drafts_from_ai(data)
    return Extraction(str(data.get("document_type") or "outro"), drafts, {"ai": data}, warnings)


def extract_file(filename: str, content: bytes, mime: str | None) -> Extraction:
    file_type, mime = _detect(filename, content, mime)

    if file_type == "xml":
        try:
            nfe = parse_nfe_xml(content)
        except NFeError as exc:
            # Outros XMLs (NFS-e, por exemplo) vão para a IA como texto.
            _require_ai("este XML")
            extraction = _from_ai([openrouter.text_part(content.decode("utf-8", "replace")[:MAX_TEXT_CHARS])])
            extraction.warnings.insert(0, f"Não é uma NF-e padrão ({exc}); lido pela IA.")
            return extraction
        return Extraction(
            "nfce" if nfe.model == "65" else "nfe",
            [draft_from_nfe(nfe)],
            {"nfe": {"access_key": nfe.access_key, "number": nfe.number, "total_cents": nfe.total_cents}},
        )

    if file_type == "pdf":
        text = extract_pdf_text(content)
        boleto = find_boleto(text)
        key = find_access_key(text)
        if openrouter.is_configured():
            if len(text) > 50:
                part = openrouter.text_part(f"Texto extraído do PDF {filename}:\n{text[:MAX_TEXT_CHARS]}")
            else:  # PDF escaneado: envia o arquivo
                part = openrouter.pdf_part(content, filename)
            extraction = _from_ai([part])
        elif boleto:
            extraction = Extraction("boleto", [], warnings=["IA não configurada; usada só a linha digitável."])
        else:
            _require_ai("este PDF")
        if boleto:
            apply_boleto(extraction.drafts, boleto)
            extraction.extracted["boleto"] = {"barcode": boleto.barcode, "line": boleto.digitable_line}
        if key and not boleto:
            for draft in extraction.drafts:
                draft.external_id = draft.external_id or key
                break
            extraction.extracted["nfe_access_key"] = key
        return extraction

    if file_type == "image":
        _require_ai("imagens")
        return _from_ai([openrouter.image_part(content, mime or "image/jpeg")])

    return extract_text(content.decode("utf-8"))


def extract_text(text: str) -> Extraction:
    stripped = text.strip()
    if not stripped:
        raise IngestError("Mensagem vazia.")
    if re.fullmatch(r"[\d\s.\-]+", stripped) and len(only_digits(stripped)) in (44, 47, 48):
        try:
            boleto = parse_boleto(stripped)
        except BoletoError as exc:
            raise IngestError(f"Linha digitável inválida: {exc}") from exc
        return Extraction("boleto", [draft_from_boleto(boleto)], {"boleto": {"barcode": boleto.barcode}})

    boleto = find_boleto(stripped)
    if not openrouter.is_configured() and boleto:
        return Extraction("boleto", [draft_from_boleto(boleto)], {"boleto": {"barcode": boleto.barcode}})
    _require_ai("mensagens de texto")
    extraction = _from_ai([openrouter.text_part(f"Mensagem do usuário:\n{stripped[:MAX_TEXT_CHARS]}")])
    if boleto:
        apply_boleto(extraction.drafts, boleto)
    return extraction


# --- gravação ----------------------------------------------------------------


def _find_similar(db: Session, draft: Draft) -> Transaction | None:
    if not draft.amount_cents:
        return None
    window = timedelta(days=SIMILAR_WINDOW_DAYS)
    start, end = draft.occurred_on - window, draft.occurred_on + window
    return db.scalars(
        select(Transaction)
        .where(
            Transaction.kind == draft.kind,
            Transaction.amount_cents == draft.amount_cents,
            or_(
                Transaction.occurred_on.between(start, end),
                Transaction.due_date.between(start, end),
            ),
        )
        .limit(1)
    ).first()


def _append_note(tx: Transaction, note: str) -> None:
    tx.notes = f"{tx.notes}\n{note}" if tx.notes else note


def _new_transaction(draft: Draft, document: Document | None) -> Transaction:
    tx = Transaction(
        kind=draft.kind,
        status=draft.status,
        amount_cents=draft.amount_cents,
        description=draft.description,
        category=resolve_category(draft.kind, draft.category, draft.description, draft.counterparty),
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
        document=document,
    )
    tx.items = [TransactionItem(**item) for item in draft.items]
    return tx


def _save_document(
    db: Session, sha: str, filename: str, content: bytes, mime: str | None, extraction: Extraction
) -> Document:
    suffix = Path(filename).suffix.lower()[:10] if filename else ""
    path = settings.upload_dir / f"{sha}{suffix}"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(content)
    document = Document(
        sha256=sha,
        filename=(filename or path.name)[:255],
        mime_type=mime,
        kind=extraction.doc_kind[:30],
        storage_path=str(path),
        extracted=extraction.extracted or None,
    )
    db.add(document)
    db.flush()
    return document


def persist(
    db: Session,
    extraction: Extraction,
    *,
    file: tuple[str, str, bytes, str | None] | None = None,
) -> IngestOutcome:
    """Grava os rascunhos. `file` = (sha256, nome, conteúdo, mime)."""
    outcome = IngestOutcome(warnings=list(extraction.warnings))
    document: Document | None = None

    def get_document() -> Document | None:
        nonlocal document
        if document is None and file is not None:
            document = _save_document(db, *file, extraction=extraction)
        return document

    for draft in extraction.drafts:
        if draft.external_id:
            existing = db.scalars(
                select(Transaction).where(Transaction.external_id == draft.external_id).order_by(Transaction.id)
            ).all()
            pending = [t for t in existing if t.status == "pending" and t.kind == draft.kind]
            if draft.status == "paid" and pending:
                tx = pending[0]
                tx.status = "paid"
                tx.occurred_on = draft.occurred_on
                tx.amount_cents = draft.amount_cents or tx.amount_cents
                tx.payment_method = draft.payment_method or tx.payment_method
                tx.account = draft.account or tx.account
                doc = get_document()
                if doc is not None:
                    tx.payment_document_id = doc.id
                _append_note(tx, f"Baixa automática pelo comprovante de {draft.occurred_on:%d/%m/%Y}.")
                outcome.updated.append(tx)
                continue
            if existing:
                outcome.duplicates.append(existing[0])
                continue

        similar = _find_similar(db, draft)
        if similar is not None:
            draft.needs_review = True
            draft.notes.append(f"Possível duplicidade com a movimentação #{similar.id}.")
        tx = _new_transaction(draft, get_document())
        db.add(tx)
        outcome.created.append(tx)

    if not extraction.drafts:
        outcome.warnings.append("Nenhuma movimentação encontrada.")
    if outcome.duplicates and not (outcome.created or outcome.updated):
        outcome.warnings.append("Documento já registrado anteriormente.")

    db.commit()
    outcome.document = document
    return outcome


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
    extraction = extract_file(filename, content, mime)
    return persist(db, extraction, file=(sha, filename, content, mime))


def ingest_text(db: Session, text: str) -> IngestOutcome:
    return persist(db, extract_text(text))
