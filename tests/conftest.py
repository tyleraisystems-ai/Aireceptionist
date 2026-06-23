import os
import tempfile

import pytest

_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.environ["RETELL_API_KEY"] = "test_secret_key"
os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"

from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, get_engine  # noqa: E402
from app.main import app  # noqa: E402

Base.metadata.create_all(bind=get_engine())


@pytest.fixture()
def client():
    return TestClient(app)


def pytest_sessionfinish(session, exitstatus):
    os.close(_db_fd)
    os.remove(_db_path)
