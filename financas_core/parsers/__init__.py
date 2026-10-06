import re
from collections.abc import Iterator

# Sequências de dígitos possivelmente separadas por espaço, ponto ou hífen,
# como aparecem em linhas digitáveis e chaves de acesso impressas.
_DIGIT_RUN = re.compile(r"\d[\d.\s-]*\d")


def digit_windows(text: str, length: int, max_run: int = 200) -> Iterator[str]:
    """Gera todas as janelas de `length` dígitos dentro de cada sequência
    numérica do texto. Quem chama valida os dígitos verificadores."""
    for match in _DIGIT_RUN.finditer(text or ""):
        digits = re.sub(r"\D", "", match.group())
        if len(digits) < length or len(digits) > max_run:
            continue
        for start in range(len(digits) - length + 1):
            yield digits[start : start + length]
