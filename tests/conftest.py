import os

os.environ.setdefault("RETELL_API_KEY", "test_api_key")

import pytest
from fastapi.testclient import TestClient
from retell.lib.webhook_auth import symmetric

from app.core.settings import get_settings
from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def sign_body():
    api_key = get_settings().retell_api_key

    def _sign(body: bytes) -> str:
        return symmetric["sign"](body.decode("utf-8"), api_key)

    return _sign
