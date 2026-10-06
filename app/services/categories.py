import unicodedata

EXPENSE_CATEGORIES = [
    "Mercado",
    "Alimentação",
    "Moradia",
    "Contas de consumo",
    "Transporte",
    "Saúde",
    "Educação",
    "Lazer",
    "Compras",
    "Serviços e assinaturas",
    "Impostos e taxas",
    "Transferências",
    "Outros",
]

INCOME_CATEGORIES = [
    "Salário",
    "Vendas e serviços prestados",
    "Rendimentos",
    "Reembolsos",
    "Transferências",
    "Outras receitas",
]

ALL_CATEGORIES = list(dict.fromkeys(EXPENSE_CATEGORIES + INCOME_CATEGORIES))

_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Mercado": ("mercado", "supermerc", "atacad", "hortifruti", "carrefour", "assai", "pao de acucar", "acougue", "padaria"),
    "Alimentação": ("restaurante", "lanchonete", "ifood", "rappi", "pizza", "burger", "cafe", "bar ", "delivery", "almoco", "jantar"),
    "Moradia": ("aluguel", "condominio", "iptu", "imobiliaria"),
    "Contas de consumo": ("energia", "eletric", "enel", "cemig", "copel", "light", "sabesp", "saneamento", "agua", "gas ", "comgas", "internet", "telefon", "vivo", "claro", "tim ", "oi "),
    "Transporte": ("uber", "99app", "99 pop", "combust", "posto", "gasolina", "etanol", "estaciona", "pedagio", "metro", "onibus", "ipva"),
    "Saúde": ("farmac", "drogaria", "droga", "hospital", "clinica", "medic", "laborat", "odonto", "plano de saude", "unimed"),
    "Educação": ("escola", "faculdade", "curso", "livraria", "mensalidade"),
    "Lazer": ("cinema", "show", "ingresso", "viagem", "hotel", "airbnb"),
    "Serviços e assinaturas": ("netflix", "spotify", "amazon prime", "disney", "youtube", "assinatura", "icloud", "google one"),
    "Impostos e taxas": ("imposto", "darf", "das ", "simples nacional", "taxa", "tarifa", "multa", "detran"),
    "Compras": ("loja", "magazine", "americanas", "shopee", "mercado livre", "amazon", "renner", "riachuelo"),
}

_INCOME_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Salário": ("salario", "folha", "pro-labore", "pro labore"),
    "Rendimentos": ("rendimento", "juros", "dividendo", "cdb", "tesouro"),
    "Reembolsos": ("reembolso", "estorno", "cashback"),
}


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c)) + " "


def guess_category(kind: str, *texts: str | None) -> str:
    haystack = _normalize(" ".join(t for t in texts if t))
    table = _INCOME_KEYWORDS if kind == "income" else _KEYWORDS
    for category, words in table.items():
        if any(word in haystack for word in words):
            return category
    return "Outras receitas" if kind == "income" else "Outros"


def resolve_category(kind: str, proposed: str | None, *texts: str | None) -> str:
    """Aceita a categoria proposta se for conhecida (ignorando acentos e
    maiúsculas); caso contrário, deduz por palavras-chave."""
    if proposed:
        wanted = _normalize(proposed).strip()
        for category in ALL_CATEGORIES:
            if _normalize(category).strip() == wanted:
                return category
    return guess_category(kind, *texts)
