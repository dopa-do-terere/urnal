import io
import logging

from pypdf import PdfReader

log = logging.getLogger(__name__)


def extract_pdf_text(content: bytes, max_pages: int = 30) -> str:
    """Texto embutido no PDF. Vazio para PDFs escaneados (só imagem)."""
    try:
        reader = PdfReader(io.BytesIO(content))
        pages = reader.pages[:max_pages]
        return "\n".join((page.extract_text() or "") for page in pages).strip()
    except Exception as exc:  # PDFs malformados levantam erros variados
        log.warning("falha ao extrair texto do PDF: %s", exc)
        return ""
