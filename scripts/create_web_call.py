"""Create a Retell web call session for manual browser testing (M6).

Creates a web call against the provisioned agent (cached agent_id from
.retell_state.json) and prints an access token plus a ready-to-open URL for
web_test/index.html, which uses the retell-client-js-sdk (via CDN, no
Node/build tooling needed) to actually join the call in a browser so you can
talk to the agent end-to-end.

Requires scripts/provision_retell_agent.py to have been run first (an
agent_id must already be cached in state).

Usage:
    python -m scripts.create_web_call
"""
from __future__ import annotations

from retell import Retell

from app.core.settings import get_settings
from scripts.provision_retell_agent import load_state


def main() -> None:
    settings = get_settings()
    state = load_state(settings.retell_state_path)
    agent_id = state.get("agent_id")
    if not agent_id:
        raise SystemExit(
            "No agent_id in .retell_state.json — run `python -m scripts.provision_retell_agent` first."
        )

    client = Retell(api_key=settings.retell_api_key)
    web_call = client.call.create_web_call(agent_id=agent_id)

    print(f"call_id: {web_call.call_id}")
    print(f"access_token: {web_call.access_token}")
    print()
    print("Microphone access requires a secure context, so file:// won't work in most")
    print("browsers. Serve the repo root over http:// instead, e.g.:")
    print("  python -m http.server 8001")
    print("then open:")
    print(f"  http://localhost:8001/web_test/index.html?token={web_call.access_token}")


if __name__ == "__main__":
    main()
