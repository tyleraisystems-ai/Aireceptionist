import httpx

from app.core.settings import Settings, get_settings

JOBBER_TOKEN_URL = "https://api.getjobber.com/api/oauth/token"
JOBBER_GRAPHQL_URL = "https://api.getjobber.com/api/graphql"
JOBBER_API_VERSION = "2023-11-15"

CLIENT_SEARCH_QUERY = """
query ClientSearch($phone: String!) {
  clients(filter: { phone: $phone }, first: 1) {
    nodes { id }
  }
}
"""

CLIENT_CREATE_MUTATION = """
mutation ClientCreate($input: ClientCreateInput!) {
  clientCreate(input: $input) {
    client { id }
    userErrors { message }
  }
}
"""

CLIENT_EDIT_MUTATION = """
mutation ClientEdit($id: EncodedId!, $input: ClientEditInput!) {
  clientEdit(clientId: $id, input: $input) {
    client { id }
    userErrors { message }
  }
}
"""


class JobberClient:
    """Client-upsert-only wrapper around Jobber's GraphQL API.

    Scoped deliberately to creating/updating the Client record (search by
    phone, create-or-update name/address) rather than full Job/Request/Quote
    creation, per the spec's narrower "Jobber CRM upsert" requirement.
    """

    def __init__(self, settings: Settings):
        self._settings = settings
        self._access_token: str | None = None

    def _fetch_access_token(self) -> str:
        response = httpx.post(
            JOBBER_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": self._settings.jobber_refresh_token,
                "client_id": self._settings.jobber_client_id,
                "client_secret": self._settings.jobber_client_secret,
            },
            timeout=10.0,
        )
        response.raise_for_status()
        return response.json()["access_token"]

    @property
    def access_token(self) -> str:
        if self._access_token is None:
            self._access_token = self._fetch_access_token()
        return self._access_token

    def _graphql(self, query: str, variables: dict) -> dict:
        response = httpx.post(
            JOBBER_GRAPHQL_URL,
            json={"query": query, "variables": variables},
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "X-JOBBER-GRAPHQL-VERSION": JOBBER_API_VERSION,
            },
            timeout=10.0,
        )
        response.raise_for_status()
        payload = response.json()
        if "errors" in payload:
            raise RuntimeError(f"Jobber GraphQL error: {payload['errors']}")
        return payload["data"]

    def _find_client_id(self, phone: str) -> str | None:
        data = self._graphql(CLIENT_SEARCH_QUERY, {"phone": phone})
        nodes = data["clients"]["nodes"]
        return nodes[0]["id"] if nodes else None

    def upsert_client(self, *, full_name: str, phone: str, address: str) -> str:
        first_name, _, last_name = full_name.partition(" ")
        existing_id = self._find_client_id(phone)
        if existing_id is None:
            data = self._graphql(
                CLIENT_CREATE_MUTATION,
                {
                    "input": {
                        "firstName": first_name,
                        "lastName": last_name or first_name,
                        "phones": [{"number": phone}],
                        "billingAddress": {"street1": address},
                    }
                },
            )
            errors = data["clientCreate"]["userErrors"]
            if errors:
                raise RuntimeError(f"Jobber clientCreate error: {errors}")
            return data["clientCreate"]["client"]["id"]

        data = self._graphql(
            CLIENT_EDIT_MUTATION,
            {
                "id": existing_id,
                "input": {
                    "firstName": first_name,
                    "lastName": last_name or first_name,
                    "billingAddress": {"street1": address},
                },
            },
        )
        errors = data["clientEdit"]["userErrors"]
        if errors:
            raise RuntimeError(f"Jobber clientEdit error: {errors}")
        return data["clientEdit"]["client"]["id"]


def get_jobber_client() -> JobberClient:
    return JobberClient(get_settings())
