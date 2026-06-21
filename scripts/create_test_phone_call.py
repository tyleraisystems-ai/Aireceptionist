"""Place an outbound test phone call from the provisioned agent (M6).

Requires a phone number already purchased and bound to this agent (Dashboard
> Phone Numbers, or `client.phone_number.create(inbound_agents=[...])` — a
real, billable action, intentionally not automated by this script). Pass
that number as --from, and the number you want to receive the test call on
as --to.

Usage:
    python -m scripts.create_test_phone_call --from +15551234567 --to +15557654321
"""
from __future__ import annotations

import argparse

from retell import Retell

from app.core.settings import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="from_number", required=True, help="Retell-owned number, E.164 format")
    parser.add_argument("--to", dest="to_number", required=True, help="Destination number to call, E.164 format")
    args = parser.parse_args()

    settings = get_settings()
    client = Retell(api_key=settings.retell_api_key)

    call = client.call.create_phone_call(from_number=args.from_number, to_number=args.to_number)
    print(f"call_id: {call.call_id}")
    print(f"call_status: {call.call_status}")
    print("Your phone should ring shortly.")


if __name__ == "__main__":
    main()
