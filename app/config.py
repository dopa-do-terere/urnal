import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from financas_core.ai import DEFAULT_BASE_URL, DEFAULT_MODEL
from financas_core.text import only_digits

load_dotenv()


@dataclass(frozen=True)
class Settings:
    database_url: str
    upload_dir: Path
    openrouter_api_key: str
    openrouter_model: str
    openrouter_base_url: str
    owner_documents: frozenset[str]
    max_upload_bytes: int


def load_settings() -> Settings:
    data_dir = Path(os.getenv("DATA_DIR", "data"))
    owner_docs = {only_digits(d) for d in os.getenv("OWNER_DOCUMENTS", "").split(",")}
    return Settings(
        database_url=os.getenv("DATABASE_URL", f"sqlite:///{data_dir / 'financas.db'}"),
        upload_dir=data_dir / "uploads",
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY", "").strip(),
        openrouter_model=os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL).strip(),
        openrouter_base_url=os.getenv("OPENROUTER_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
        owner_documents=frozenset(d for d in owner_docs if d),
        max_upload_bytes=int(os.getenv("MAX_UPLOAD_MB", "20")) * 1024 * 1024,
    )


settings = load_settings()
