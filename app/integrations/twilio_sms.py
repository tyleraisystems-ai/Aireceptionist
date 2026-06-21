import httpx

from app.core.settings import Settings, get_settings

TWILIO_API_BASE = "https://api.twilio.com/2010-04-01"


class TwilioSmsClient:
    """Thin wrapper around Twilio's REST API for sending a single SMS.

    Direct httpx call rather than the twilio SDK since sending one message
    is a single authenticated POST and doesn't warrant a full SDK dependency.
    """

    def __init__(self, settings: Settings):
        self._settings = settings

    def send_sms(self, to: str, body: str) -> str:
        url = f"{TWILIO_API_BASE}/Accounts/{self._settings.twilio_account_sid}/Messages.json"
        response = httpx.post(
            url,
            data={"To": to, "From": self._settings.twilio_from_number, "Body": body},
            auth=(self._settings.twilio_account_sid, self._settings.twilio_auth_token),
            timeout=10.0,
        )
        response.raise_for_status()
        return response.json()["sid"]


def get_twilio_client() -> TwilioSmsClient:
    return TwilioSmsClient(get_settings())
