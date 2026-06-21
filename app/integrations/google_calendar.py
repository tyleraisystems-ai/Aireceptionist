import json
from datetime import datetime, timedelta

from google.oauth2 import service_account
from googleapiclient.discovery import build

from app.core.settings import Settings, get_settings

SCOPES = ["https://www.googleapis.com/auth/calendar"]
SLOT_DURATION = timedelta(hours=2)


class GoogleCalendarClient:
    """Thin wrapper around the Calendar API. Endpoints depend on this via
    `get_calendar_client` so tests can swap in a fake without network calls.
    """

    def __init__(self, settings: Settings):
        self._settings = settings
        self._service = None

    @property
    def calendar_id(self) -> str:
        return self._settings.google_calendar_id

    def _build_service(self):
        raw = self._settings.google_calendar_credentials_json
        info = json.loads(raw) if raw.strip().startswith("{") else json.loads(open(raw, encoding="utf-8").read())
        credentials = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
        return build("calendar", "v3", credentials=credentials, cache_discovery=False)

    @property
    def service(self):
        if self._service is None:
            self._service = self._build_service()
        return self._service

    def find_open_slots(
        self,
        business_hours: dict[str, str],
        search_days: int = 5,
        max_results: int = 2,
        slot_duration: timedelta = SLOT_DURATION,
        now: datetime | None = None,
    ) -> list[tuple[datetime, datetime]]:
        now = now or datetime.now().astimezone()
        window_end = now + timedelta(days=search_days)

        busy = self.service.freebusy().query(
            body={
                "timeMin": now.isoformat(),
                "timeMax": window_end.isoformat(),
                "items": [{"id": self.calendar_id}],
            }
        ).execute()
        busy_periods = [
            (datetime.fromisoformat(b["start"]), datetime.fromisoformat(b["end"]))
            for b in busy["calendars"][self.calendar_id]["busy"]
        ]

        candidates: list[tuple[datetime, datetime]] = []
        day = now
        weekday_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for day_offset in range(search_days + 1):
            current_day = (day + timedelta(days=day_offset)).date()
            weekday = weekday_names[current_day.weekday()]
            hours = business_hours.get(weekday, "Closed")
            if hours.lower() == "closed":
                continue

            open_str, close_str = [h.strip() for h in hours.split("-")]
            day_open = _combine(current_day, open_str, now.tzinfo)
            day_close = _combine(current_day, close_str, now.tzinfo)

            cursor = max(day_open, now)
            while cursor + slot_duration <= day_close:
                candidate_end = cursor + slot_duration
                if not _overlaps(cursor, candidate_end, busy_periods):
                    candidates.append((cursor, candidate_end))
                    if len(candidates) >= max_results:
                        return candidates
                cursor += slot_duration

        return candidates

    def create_event(self, summary: str, description: str, start: datetime, end: datetime) -> str:
        event = self.service.events().insert(
            calendarId=self.calendar_id,
            body={
                "summary": summary,
                "description": description,
                "start": {"dateTime": start.isoformat()},
                "end": {"dateTime": end.isoformat()},
            },
        ).execute()
        return event["id"]

    def update_event(self, event_id: str, start: datetime, end: datetime) -> None:
        self.service.events().patch(
            calendarId=self.calendar_id,
            eventId=event_id,
            body={
                "start": {"dateTime": start.isoformat()},
                "end": {"dateTime": end.isoformat()},
            },
        ).execute()

    def delete_event(self, event_id: str) -> None:
        self.service.events().delete(calendarId=self.calendar_id, eventId=event_id).execute()


def _combine(date_, time_str: str, tzinfo):
    parsed = datetime.strptime(time_str.strip(), "%I:%M %p")
    return datetime(date_.year, date_.month, date_.day, parsed.hour, parsed.minute, tzinfo=tzinfo)


def _overlaps(start: datetime, end: datetime, busy_periods: list[tuple[datetime, datetime]]) -> bool:
    return any(start < b_end and end > b_start for b_start, b_end in busy_periods)


def get_calendar_client() -> GoogleCalendarClient:
    return GoogleCalendarClient(get_settings())
