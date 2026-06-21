import os
import uuid
from datetime import datetime, timedelta, timezone

os.environ.setdefault("RETELL_API_KEY", "test_api_key")

import pytest
from fastapi.testclient import TestClient
from retell.lib.webhook_auth import symmetric

from app.core.settings import get_settings
from app.db.session import SessionLocal, engine, get_db
from app.integrations.google_calendar import get_calendar_client
from app.integrations.jobber import get_jobber_client
from app.integrations.twilio_sms import get_twilio_client
from app.main import app


@pytest.fixture
def sign_body():
    api_key = get_settings().retell_api_key

    def _sign(body: bytes) -> str:
        return symmetric["sign"](body.decode("utf-8"), api_key)

    return _sign


@pytest.fixture
def db_session():
    """Each test runs inside a transaction that's rolled back afterwards, so
    Postgres state never leaks between tests.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = SessionLocal(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


class FakeGoogleCalendarClient:
    """In-memory stand-in for GoogleCalendarClient so tests don't need real
    Google credentials or network access.
    """

    def __init__(self):
        self.events: dict[str, dict] = {}
        self._next_id = 1
        now = datetime.now(timezone.utc) + timedelta(days=1)
        self.canned_slots = [
            (now.replace(hour=9, minute=0, second=0, microsecond=0), now.replace(hour=11, minute=0, second=0, microsecond=0)),
            (now.replace(hour=13, minute=0, second=0, microsecond=0), now.replace(hour=15, minute=0, second=0, microsecond=0)),
        ]

    def find_open_slots(self, **kwargs):
        return self.canned_slots

    def create_event(self, summary, description, start, end):
        event_id = f"evt-{self._next_id}"
        self._next_id += 1
        self.events[event_id] = {"summary": summary, "description": description, "start": start, "end": end}
        return event_id

    def update_event(self, event_id, start, end):
        self.events[event_id]["start"] = start
        self.events[event_id]["end"] = end

    def delete_event(self, event_id):
        self.events.pop(event_id, None)


@pytest.fixture
def fake_calendar():
    return FakeGoogleCalendarClient()


class FakeTwilioClient:
    """In-memory stand-in for TwilioSmsClient so tests don't need real
    Twilio credentials or network access.
    """

    def __init__(self):
        self.sent: list[tuple[str, str]] = []

    def send_sms(self, to: str, body: str) -> str:
        self.sent.append((to, body))
        return f"sms-{len(self.sent)}"


@pytest.fixture
def fake_twilio():
    return FakeTwilioClient()


class FakeJobberClient:
    """In-memory stand-in for JobberClient so tests don't need real Jobber
    credentials or network access.
    """

    def __init__(self):
        self.clients: dict[str, dict] = {}

    def upsert_client(self, *, full_name: str, phone: str, address: str) -> str:
        client_id = self.clients.get(phone, {}).get("id") or f"client-{len(self.clients) + 1}"
        self.clients[phone] = {"id": client_id, "full_name": full_name, "address": address}
        return client_id


@pytest.fixture
def fake_jobber():
    return FakeJobberClient()


@pytest.fixture
def client(db_session, fake_calendar, fake_twilio, fake_jobber) -> TestClient:
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_calendar_client] = lambda: fake_calendar
    app.dependency_overrides[get_twilio_client] = lambda: fake_twilio
    app.dependency_overrides[get_jobber_client] = lambda: fake_jobber
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def retell_call_id():
    return f"call_{uuid.uuid4().hex}"
