"""Teste ponta a ponta contra os emuladores, simulando o app:

    scripts/sync-core.sh
    firebase emulators:exec --project demo-financas "python3 scripts/e2e_emulators.py"
"""

import sys
import uuid
from datetime import date
from pathlib import Path
from urllib.parse import quote

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.helpers import make_access_key, make_bancario_line, make_nfe_xml  # noqa: E402

PROJECT = "demo-financas"
REGION = "southamerica-east1"
BUCKET = f"{PROJECT}.appspot.com"
AUTH = "http://127.0.0.1:9099/identitytoolkit.googleapis.com/v1"
FUNCTIONS = f"http://127.0.0.1:5001/{PROJECT}/{REGION}"
FIRESTORE = f"http://127.0.0.1:8080/v1/projects/{PROJECT}/databases/(default)/documents"
STORAGE = f"http://127.0.0.1:9199/v0/b/{BUCKET}/o"

http = httpx.Client(timeout=120, trust_env=False)


def sign_up() -> tuple[str, str]:
    res = http.post(f"{AUTH}/accounts:signUp?key=fake", json={
        "email": f"{uuid.uuid4().hex[:8]}@teste.com", "password": "segredo123", "returnSecureToken": True,
    })
    res.raise_for_status()
    body = res.json()
    return body["localId"], body["idToken"]


def call(name: str, token: str | None, data: dict) -> httpx.Response:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return http.post(f"{FUNCTIONS}/{name}", json={"data": data}, headers=headers)


def check(condition: bool, message: str) -> None:
    print(("OK   " if condition else "FALHA") + " " + message)
    if not condition:
        sys.exit(1)


def main() -> None:
    uid, token = sign_up()
    other_uid, other_token = sign_up()

    res = call("ingest_text", None, {"text": "oi"})
    check(res.status_code == 401, "função recusa chamada sem login")

    line = make_bancario_line(18990, date(2026, 11, 10))
    res = call("ingest_text", token, {"text": line})
    created = res.json()["result"]["created"]
    check(res.status_code == 200 and created[0]["amount_cents"] == 18990, "linha digitável registrada")

    res = call("ingest_text", token, {"text": "gastei 10 reais no mercado"})
    check(res.status_code == 400 and "OPENROUTER_API_KEY" in res.text, "sem IA, texto livre dá erro claro")

    path = f"users/{uid}/uploads/{uuid.uuid4().hex}-nota.xml"
    res = http.post(
        f"{STORAGE}?name={quote(path, safe='')}",
        content=make_nfe_xml(make_access_key()),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "text/xml"},
    )
    check(res.status_code == 200, "upload para o Storage permitido no próprio diretório")

    res = http.post(
        f"{STORAGE}?name={quote(f'users/{uid}/uploads/x.xml', safe='')}",
        content=b"<x/>",
        headers={"Authorization": f"Bearer {other_token}", "Content-Type": "text/xml"},
    )
    check(res.status_code in (401, 403), "upload no diretório de outro usuário bloqueado")

    res = call("ingest_file", token, {"path": path, "filename": "nota.xml"})
    result = res.json().get("result", {})
    check(res.status_code == 200 and result["created"][0]["category"] == "Mercado", "NF-e lida pela função")

    res = call("ingest_file", other_token, {"path": path})
    check(res.status_code == 400, "função recusa arquivo de outro usuário")

    auth = {"Authorization": f"Bearer {token}"}
    res = http.get(f"{FIRESTORE}/users/{uid}/transactions", headers=auth)
    docs = res.json().get("documents", [])
    check(res.status_code == 200 and len(docs) == 2, "usuário lê as próprias movimentações")

    res = http.get(f"{FIRESTORE}/users/{uid}/transactions", headers={"Authorization": f"Bearer {other_token}"})
    check(res.status_code == 403, "outro usuário não lê as movimentações")

    def fields(**values):
        out = {}
        for key, value in values.items():
            if isinstance(value, bool):
                out[key] = {"booleanValue": value}
            elif isinstance(value, int):
                out[key] = {"integerValue": str(value)}
            elif value is None:
                out[key] = {"nullValue": None}
            else:
                out[key] = {"stringValue": value}
        return {"fields": out}

    good = fields(kind="expense", status="paid", amount_cents=4590, description="Padaria", category="Mercado",
                  occurred_on="2026-10-06", due_date=None, needs_review=False, source="manual")
    res = http.post(f"{FIRESTORE}/users/{uid}/transactions", headers=auth, json=good)
    check(res.status_code == 200, "lançamento manual válido aceito")

    bad = fields(kind="expense", status="paid", amount_cents=-5, description="X", category="Outros",
                 occurred_on="2026-10-06", needs_review=False)
    res = http.post(f"{FIRESTORE}/users/{uid}/transactions", headers=auth, json=bad)
    check(res.status_code == 403, "valor negativo recusado pelas regras")

    bad = fields(kind="expense", status="paid", amount_cents=100, description="X", category="Outros",
                 occurred_on="06/10/2026", needs_review=False)
    res = http.post(f"{FIRESTORE}/users/{uid}/transactions", headers=auth, json=bad)
    check(res.status_code == 403, "data fora do formato recusada pelas regras")

    res = http.post(f"{FIRESTORE}/users/{uid}/documents", headers=auth, json=fields(filename="x"))
    check(res.status_code == 403, "app não escreve metadados de documentos")

    print("Tudo certo.")


if __name__ == "__main__":
    main()
