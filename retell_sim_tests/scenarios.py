"""Simulation test scenarios for the HVAC receptionist Conversation Flow.

Each scenario becomes a Retell test case definition (`client.tests.*`): a
simulated caller persona (`user_prompt`) run end-to-end against the live
conversation flow. `tool_mocks` short-circuit our Custom Function calls with
canned responses so a run doesn't need a publicly reachable backend, and
`metrics` names the dashboard-configured evaluation metric(s) to score the
run against (must match metric names configured in the Retell dashboard's
Evaluation Metrics — adjust DEFAULT_METRICS if your account uses different
names).
"""
from __future__ import annotations

import json
from typing import Any

DEFAULT_METRICS = ["task_completion"]


def _mock(
    tool_name: str, output: dict[str, Any], *, match_args: dict[str, Any] | None = None, result: bool | None = None
) -> dict[str, Any]:
    rule: dict[str, Any] = {"args": match_args, "type": "partial_match"} if match_args else {"type": "any"}
    mock: dict[str, Any] = {"tool_name": tool_name, "input_match_rule": rule, "output": json.dumps(output)}
    if result is not None:
        mock["result"] = result
    return mock


SCENARIOS: list[dict[str, Any]] = [
    {
        "name": "routine_booking_happy_path",
        "user_prompt": (
            "You are a homeowner calling because your AC isn't cooling well. It is not an "
            "emergency. You don't smell gas. When the receptionist offers an appointment "
            "time, accept the first one offered. When asked, give your name as Jamie "
            "Rivera, callback number 555-0142, and address 14 Oak Lane."
        ),
        "metrics": DEFAULT_METRICS,
        "tool_mocks": [
            _mock(
                "check_availability",
                {"slots": [{"start": "2026-06-22T09:00:00-05:00", "end": "2026-06-22T11:00:00-05:00"}]},
            ),
            _mock(
                "book_visit",
                {
                    "appointment_id": "sim-appt-1",
                    "confirmed_start": "2026-06-22T09:00:00-05:00",
                    "confirmed_end": "2026-06-22T11:00:00-05:00",
                },
            ),
        ],
    },
    {
        "name": "urgent_no_heat_emergency",
        "user_prompt": (
            "You are calling because your furnace is completely dead and it's freezing "
            "inside your house. This is urgent. You don't smell gas. Give your name as "
            "Morgan Lee, callback number 555-0177, and address 9 Birch Court when asked."
        ),
        "metrics": DEFAULT_METRICS,
        "tool_mocks": [
            _mock("flag_emergency", {"lead_id": "sim-lead-1", "disposition": "EMERGENCY_FLAGGED"}),
        ],
    },
    {
        "name": "gas_smell_immediate_safety_response",
        "user_prompt": (
            "As soon as the receptionist greets you, say that you smell a strong gas odor "
            "near your furnace right now. Do not discuss booking an appointment."
        ),
        "metrics": DEFAULT_METRICS,
        "tool_mocks": [],
    },
    {
        "name": "reschedule_existing_appointment",
        "user_prompt": (
            "You already have an appointment booked and you're calling to move it to a "
            "later time this week. Your callback number is 555-0188. Accept whatever new "
            "time the receptionist proposes."
        ),
        "metrics": DEFAULT_METRICS,
        "tool_mocks": [
            _mock(
                "reschedule_visit",
                {
                    "appointment_id": "sim-appt-2",
                    "confirmed_start": "2026-06-23T13:00:00-05:00",
                    "confirmed_end": "2026-06-23T15:00:00-05:00",
                },
            ),
        ],
    },
    {
        "name": "cancel_existing_appointment",
        "user_prompt": (
            "You need to cancel your upcoming HVAC appointment because you sold the house. "
            "Your callback number is 555-0199."
        ),
        "metrics": DEFAULT_METRICS,
        "tool_mocks": [
            _mock("cancel_visit", {"appointment_id": "sim-appt-3", "status": "CANCELLED"}),
        ],
    },
    {
        "name": "faq_pricing_never_quotes_exact_price",
        "user_prompt": (
            "Ask the receptionist exactly how much a repair will cost, and push back twice "
            "asking for a specific dollar figure or a ballpark number before giving up and "
            "ending the call politely."
        ),
        "metrics": DEFAULT_METRICS,
        "tool_mocks": [],
    },
    {
        "name": "transfer_to_human_on_explicit_request",
        "user_prompt": (
            "Immediately say you don't want to talk to a robot and ask to speak to a real "
            "person right away."
        ),
        "metrics": DEFAULT_METRICS,
        "tool_mocks": [
            _mock("transfer_to_human", {"transfer_to": "+15555550100"}),
        ],
    },
    {
        "name": "recording_objection_routes_to_human",
        "user_prompt": (
            "As soon as you hear that the call may be recorded, say you do not consent to "
            "being recorded and ask to speak to a person instead."
        ),
        "metrics": DEFAULT_METRICS,
        "tool_mocks": [
            _mock("transfer_to_human", {"transfer_to": "+15555550100"}),
        ],
    },
    {
        "name": "routine_no_offered_time_works_falls_back_to_lead_capture",
        "user_prompt": (
            "You're calling about a routine maintenance tune-up. No matter what appointment "
            "times are offered, say none of them work for your schedule, then provide your "
            "name as Casey Nguyen, callback number 555-0166, and address 3 Maple Way so they "
            "can call you back instead."
        ),
        "metrics": DEFAULT_METRICS,
        "tool_mocks": [
            _mock(
                "check_availability",
                {"slots": [{"start": "2026-06-22T09:00:00-05:00", "end": "2026-06-22T11:00:00-05:00"}]},
            ),
            _mock("capture_lead", {"lead_id": "sim-lead-2"}),
        ],
    },
]
