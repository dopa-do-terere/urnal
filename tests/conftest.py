import os
import tempfile

# Configura o ambiente antes de importar a aplicação.
_tmp = tempfile.mkdtemp(prefix="financas-test-")
os.environ["DATA_DIR"] = _tmp
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["OPENROUTER_API_KEY"] = ""
os.environ["OWNER_DOCUMENTS"] = "12345678909"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(engine)
