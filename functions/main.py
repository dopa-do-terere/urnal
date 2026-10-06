"""Cloud Functions do Assistente de Finanças.

O app chama estas funções com o Firebase Auth do usuário logado:

- ingest_text({"text": "..."}): mensagem livre ou linha digitável.
- ingest_file({"path": "users/<uid>/uploads/<arquivo>", "filename": "..."}):
  arquivo que o app acabou de enviar ao Storage.

As duas devolvem {"created", "updated", "duplicates", "warnings", "document"}.
"""

import logging
import os

from firebase_admin import credentials, firestore, initialize_app, storage
from firebase_functions import https_fn, options
from firebase_functions.params import SecretParam, StringParam
from google.api_core.exceptions import NotFound
from google.auth.credentials import AnonymousCredentials

from financas_core.ai import DEFAULT_MODEL, AIConfig, OpenRouterClient
from financas_core.extraction import Extractor, IngestError
from firestore_store import MAX_UPLOAD_BYTES, ingest_message, ingest_uploaded_file


class _EmulatorCredential(credentials.Base):
    """Nos emuladores não há credencial do Google; o SDK aceita anônima."""

    def get_credential(self):
        return AnonymousCredentials()


initialize_app(_EmulatorCredential() if os.environ.get("FUNCTIONS_EMULATOR") == "true" else None)
log = logging.getLogger(__name__)

REGION = "southamerica-east1"
OPENROUTER_API_KEY = SecretParam("OPENROUTER_API_KEY")
OPENROUTER_MODEL = StringParam("OPENROUTER_MODEL", default=DEFAULT_MODEL)

options.set_global_options(region=REGION, max_instances=10)


def _ai() -> Extractor | None:
    key = (OPENROUTER_API_KEY.value or "").strip()
    # "off" desliga a IA (útil nos emuladores, em functions/.secret.local).
    if not key or key.lower() == "off":
        return None
    return OpenRouterClient(AIConfig(api_key=key, model=OPENROUTER_MODEL.value or DEFAULT_MODEL))


def _user_ref(req: https_fn.CallableRequest):
    if req.auth is None:
        raise https_fn.HttpsError(https_fn.FunctionsErrorCode.UNAUTHENTICATED, "Faça login para continuar.")
    return firestore.client().collection("users").document(req.auth.uid)


def _failed(exc: IngestError) -> https_fn.HttpsError:
    return https_fn.HttpsError(https_fn.FunctionsErrorCode.FAILED_PRECONDITION, str(exc))


@https_fn.on_call(secrets=[OPENROUTER_API_KEY], memory=options.MemoryOption.MB_512, timeout_sec=120)
def ingest_text(req: https_fn.CallableRequest) -> dict:
    user_ref = _user_ref(req)
    text = str((req.data or {}).get("text") or "")
    if not text.strip() or len(text) > 60_000:
        raise https_fn.HttpsError(https_fn.FunctionsErrorCode.INVALID_ARGUMENT, "Mensagem vazia ou longa demais.")
    try:
        return ingest_message(user_ref, text, _ai())
    except IngestError as exc:
        raise _failed(exc) from exc


@https_fn.on_call(secrets=[OPENROUTER_API_KEY], memory=options.MemoryOption.GB_1, timeout_sec=300)
def ingest_file(req: https_fn.CallableRequest) -> dict:
    user_ref = _user_ref(req)
    data = req.data or {}
    path = str(data.get("path") or "")
    prefix = f"users/{req.auth.uid}/uploads/"
    if not path.startswith(prefix) or ".." in path or len(path) > 600:
        raise https_fn.HttpsError(https_fn.FunctionsErrorCode.INVALID_ARGUMENT, "Caminho de arquivo inválido.")

    blob = storage.bucket().blob(path)
    try:
        blob.reload()
    except NotFound as exc:
        raise https_fn.HttpsError(https_fn.FunctionsErrorCode.NOT_FOUND, "Arquivo não encontrado.") from exc
    if (blob.size or 0) > MAX_UPLOAD_BYTES:
        blob.delete()
        raise https_fn.HttpsError(https_fn.FunctionsErrorCode.INVALID_ARGUMENT, "Arquivo maior que 20 MB.")

    filename = str(data.get("filename") or path.removeprefix(prefix))[:255]
    try:
        return ingest_uploaded_file(
            user_ref,
            path=path,
            filename=filename,
            content=blob.download_as_bytes(),
            mime=blob.content_type,
            ai=_ai(),
            delete_upload=blob.delete,
        )
    except IngestError as exc:
        raise _failed(exc) from exc
