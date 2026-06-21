"""Provision the Retell Conversation Flow agent for the HVAC receptionist.

Creates (or updates, on rerun) the Retell Knowledge Base, Conversation Flow,
and Agent via the Retell API, so the agent configuration is reproducible and
lives in git instead of only in the Retell dashboard.

Idempotency: resource IDs returned by the first successful run are cached in
a local, gitignored state file (see Settings.retell_state_path, default
`.retell_state.json`). Reruns `update()` those resources instead of creating
duplicates. The Knowledge Base has no update endpoint in the SDK, so it is
recreated (delete + create) only when the FAQ content actually changed
(tracked via a content hash in the state file).

Steps that CANNOT be done via this script (must be done in the Retell
dashboard, see README "M3 dashboard steps"):
  - Picking a `voice_id` / previewing voices (Dashboard > Voice Library, or
    `retell.voice.list()` with a real API key). Set the chosen id as
    RETELL_VOICE_ID in .env before running this script.
  - Buying/assigning a phone number to this agent (Dashboard > Phone Numbers,
    or `retell.phone_number.create()`), and pointing it at the agent created
    here.
  - Two-party-consent recording disclosure wording review, and final sign-off
    on the AI-disclosure greeting language, before going live in a two-party
    consent state.
  - LLM Playground / Web Call / Phone Call testing (M6).

Usage:
    python -m scripts.provision_retell_agent
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from retell import Retell

from app.core.business_config import get_business_config
from app.core.settings import get_settings

FUNCTION_TOOL_DEFS: list[dict[str, Any]] = [
    {
        "name": "check_availability",
        "url_path": "/functions/check-availability",
        "description": "Look up the next available appointment windows for a routine HVAC visit.",
        "parameters": {
            "type": "object",
            "properties": {
                "preferred_window": {
                    "type": "string",
                    "description": "Caller's preferred timing, e.g. 'this week' or 'tomorrow morning'. Optional.",
                }
            },
        },
    },
    {
        "name": "book_visit",
        "url_path": "/functions/book-visit",
        "description": "Book a service visit once the caller has agreed to a specific offered time.",
        "parameters": {
            "type": "object",
            "properties": {
                "full_name": {"type": "string"},
                "callback_number": {"type": "string"},
                "service_address": {"type": "string"},
                "issue_summary": {"type": "string", "description": "One-sentence summary of the issue."},
                "urgency": {"type": "string", "enum": ["URGENT", "ROUTINE"]},
                "start": {"type": "string", "description": "ISO 8601 start time, must match an offered slot."},
                "end": {"type": "string", "description": "ISO 8601 end time, must match an offered slot."},
            },
            "required": [
                "full_name",
                "callback_number",
                "service_address",
                "issue_summary",
                "urgency",
                "start",
                "end",
            ],
        },
    },
    {
        "name": "reschedule_visit",
        "url_path": "/functions/reschedule-visit",
        "description": "Reschedule an existing booked appointment to a new time.",
        "parameters": {
            "type": "object",
            "properties": {
                "callback_number": {"type": "string"},
                "appointment_id": {"type": "string", "description": "If known; otherwise looked up by phone number."},
                "new_start": {"type": "string", "description": "ISO 8601"},
                "new_end": {"type": "string", "description": "ISO 8601"},
            },
            "required": ["callback_number", "new_start", "new_end"],
        },
    },
    {
        "name": "cancel_visit",
        "url_path": "/functions/cancel-visit",
        "description": "Cancel an existing booked appointment.",
        "parameters": {
            "type": "object",
            "properties": {
                "callback_number": {"type": "string"},
                "appointment_id": {"type": "string", "description": "If known; otherwise looked up by phone number."},
            },
            "required": ["callback_number"],
        },
    },
    {
        "name": "capture_lead",
        "url_path": "/functions/capture-lead",
        "description": "Record a routine lead when no offered appointment time works for the caller.",
        "parameters": {
            "type": "object",
            "properties": {
                "full_name": {"type": "string"},
                "callback_number": {"type": "string"},
                "service_address": {"type": "string"},
                "issue_summary": {"type": "string"},
                "urgency": {"type": "string", "enum": ["URGENT", "ROUTINE"]},
            },
            "required": ["full_name", "callback_number", "service_address", "issue_summary", "urgency"],
        },
    },
    {
        "name": "flag_emergency",
        "url_path": "/functions/flag-emergency",
        "description": "Flag an urgent HVAC issue (fully down system, no heat in cold, no cooling in heat) for immediate human callback.",
        "parameters": {
            "type": "object",
            "properties": {
                "full_name": {"type": "string"},
                "callback_number": {"type": "string"},
                "service_address": {"type": "string"},
                "issue_summary": {"type": "string"},
                "reason": {"type": "string", "description": "Why this is urgent."},
            },
            "required": ["full_name", "callback_number", "service_address", "issue_summary", "reason"],
        },
    },
    {
        "name": "transfer_to_human",
        "url_path": "/functions/transfer-to-human",
        "description": "Get the phone number to transfer this call to a human (on-call staff).",
        "parameters": {
            "type": "object",
            "properties": {
                "caller_number": {"type": "string"},
                "reason": {"type": "string", "description": "Why a human is needed. Optional."},
            },
            "required": ["caller_number"],
        },
        "response_variables": {"transfer_to": "$.result.transfer_to"},
    },
]

GLOBAL_PROMPT_TEMPLATE = """\
You are the AI voice receptionist for {business_name}, an HVAC company \
serving {service_area}. Business hours: {hours_summary}.

Hard rules, no exceptions:
- If asked whether you are an AI, say yes — you are an AI assistant for {business_name}.
- Never quote an exact price. Pricing is always confirmed in person by a technician.
- Never diagnose the HVAC problem yourself.
- Never promise an exact arrival time; only offer the appointment window itself.
- If the caller sounds upset, confused, or explicitly asks for a person, offer \
to transfer them to a human right away.
- If the caller objects to, declines, or asks to opt out of the call being \
recorded, do not argue or try to talk them out of it — immediately offer to \
transfer them to a human instead, since recording cannot be turned off \
mid-call.
- If the caller says they smell gas at any point, stop everything else and \
follow the gas safety procedure immediately — never steer a gas-smell caller \
toward booking an appointment.
"""

GAS_EMERGENCY_GLOBAL_CONDITION = (
    "The caller mentions smelling gas, a gas leak, or a strong gas odor at any "
    "point in the conversation, no matter what else is being discussed."
)
HUMAN_TRANSFER_GLOBAL_CONDITION = (
    "The caller is upset, confused, frustrated, explicitly asks to speak to a "
    "person/human/representative, objects to or declines the call being "
    "recorded, or the agent is otherwise unable to help them."
)


def _edge(edge_id: str, prompt: str, destination_node_id: str) -> dict[str, Any]:
    return {
        "id": edge_id,
        "transition_condition": {"type": "prompt", "prompt": prompt},
        "destination_node_id": destination_node_id,
    }


def _always_edge(edge_id: str, destination_node_id: str) -> dict[str, Any]:
    return {
        "id": edge_id,
        "transition_condition": {"type": "prompt", "prompt": "Always"},
        "destination_node_id": destination_node_id,
    }


def _else_edge(edge_id: str, destination_node_id: str) -> dict[str, Any]:
    return {
        "id": edge_id,
        "transition_condition": {"type": "prompt", "prompt": "None of the above conditions match."},
        "destination_node_id": destination_node_id,
    }


def _conversation_node(
    node_id: str,
    prompt: str,
    *,
    edges: list[dict[str, Any]] | None = None,
    else_edge_destination: str | None = None,
    always_edge_destination: str | None = None,
    global_condition: str | None = None,
) -> dict[str, Any]:
    node: dict[str, Any] = {
        "id": node_id,
        "type": "conversation",
        "instruction": {"type": "prompt", "text": prompt},
    }
    if edges:
        node["edges"] = edges
    if else_edge_destination:
        node["else_edge"] = _else_edge(f"{node_id}__else", else_edge_destination)
    if always_edge_destination:
        node["always_edge"] = _always_edge(f"{node_id}__always", always_edge_destination)
    if global_condition:
        node["global_node_setting"] = {"condition": global_condition}
    return node


def _function_node(
    node_id: str,
    tool_id: str,
    *,
    always_edge_destination: str,
    global_condition: str | None = None,
) -> dict[str, Any]:
    node: dict[str, Any] = {
        "id": node_id,
        "type": "function",
        "tool_id": tool_id,
        "tool_type": "shared",
        "wait_for_result": True,
        "always_edge": _always_edge(f"{node_id}__always", always_edge_destination),
    }
    if global_condition:
        node["global_node_setting"] = {"condition": global_condition}
    return node


def build_tools(backend_base_url: str) -> list[dict[str, Any]]:
    tools = []
    for spec in FUNCTION_TOOL_DEFS:
        tool: dict[str, Any] = {
            "tool_id": spec["name"],
            "name": spec["name"],
            "type": "custom",
            "url": backend_base_url.rstrip("/") + spec["url_path"],
            "description": spec["description"],
            "method": "POST",
            "parameters": spec["parameters"],
            "speak_during_execution": True,
            "speak_after_execution": True,
            "timeout_ms": 8000,
        }
        if "response_variables" in spec:
            tool["response_variables"] = spec["response_variables"]
        tools.append(tool)
    return tools


def build_nodes(business: dict[str, Any]) -> list[dict[str, Any]]:
    collect_instruction = (
        "Collect the caller's full name, callback phone number, service address, "
        "and a one-sentence summary of the issue. Ask for these one at a time, "
        "do not ask for more than one piece of information per turn. Once you "
        "have the phone number and address, read them back to the caller to "
        "confirm you captured them correctly before moving on."
    )

    nodes = [
        _conversation_node(
            "greet",
            business["greeting_script"],
            edges=[
                _edge(
                    "greet__existing",
                    "Caller wants to check on, reschedule, or cancel an existing appointment.",
                    "manage_existing",
                )
            ],
            else_edge_destination="gas_safety",
        ),
        _conversation_node(
            "gas_safety",
            business["gas_safety_script"],
            edges=[
                _edge(
                    "gas_safety__yes",
                    "Caller indicates yes, they do smell gas or a strong odor.",
                    "gas_emergency_end",
                )
            ],
            else_edge_destination="triage",
            global_condition=GAS_EMERGENCY_GLOBAL_CONDITION,
        ),
        {
            "id": "gas_emergency_end",
            "type": "end",
            "instruction": {"type": "static_text", "text": business["gas_emergency_response"]},
            "speak_during_execution": True,
        },
        _conversation_node(
            "triage",
            "Ask enough to determine urgency: is the system completely down, is "
            "there no heat during cold weather, or no cooling during extreme heat? "
            "Those are urgent. Anything else (routine maintenance, minor issue, "
            "tune-up) is routine.",
            edges=[
                _edge(
                    "triage__urgent",
                    "System is completely down, no heat in cold weather, or no "
                    "cooling in extreme heat (urgent safety/comfort issue).",
                    "collect_urgent",
                )
            ],
            else_edge_destination="collect_routine",
        ),
        _conversation_node("collect_urgent", collect_instruction, always_edge_destination="flag_emergency_fn"),
        _conversation_node("collect_routine", collect_instruction, always_edge_destination="check_availability_fn"),
        _function_node("flag_emergency_fn", "flag_emergency", always_edge_destination="confirm_urgent"),
        _function_node("check_availability_fn", "check_availability", always_edge_destination="offer_times"),
        _conversation_node(
            "offer_times",
            "Offer the caller the available appointment times returned by "
            "check_availability and ask which one works for them.",
            edges=[
                _edge(
                    "offer_times__picked",
                    "Caller agrees to or picks one of the offered appointment times.",
                    "book_visit_fn",
                )
            ],
            else_edge_destination="capture_lead_fn",
        ),
        _function_node("book_visit_fn", "book_visit", always_edge_destination="confirm_routine"),
        _function_node("capture_lead_fn", "capture_lead", always_edge_destination="confirm_no_match"),
        _conversation_node(
            "manage_existing",
            "Ask whether the caller wants to reschedule or cancel their existing "
            "appointment.",
            edges=[
                _edge("manage_existing__reschedule", "Caller wants to reschedule their appointment.", "reschedule_visit_fn"),
                _edge("manage_existing__cancel", "Caller wants to cancel their appointment.", "cancel_visit_fn"),
            ],
            else_edge_destination="gas_safety",
        ),
        _function_node("reschedule_visit_fn", "reschedule_visit", always_edge_destination="confirm_reschedule"),
        _function_node("cancel_visit_fn", "cancel_visit", always_edge_destination="confirm_cancel"),
        _conversation_node(
            "confirm_urgent",
            "Read back the caller's name, phone number, address, and issue. Tell "
            "them a technician will call them back shortly because this is "
            "urgent, and that you're texting a confirmation now.",
            always_edge_destination="close",
        ),
        _conversation_node(
            "confirm_routine",
            "Read back the booked appointment date/time and address to confirm. "
            "Tell them you're texting a confirmation now.",
            always_edge_destination="close",
        ),
        _conversation_node(
            "confirm_no_match",
            "Let the caller know none of the offered times worked, but their "
            "information has been saved and a team member will follow up to "
            "find a time that works.",
            always_edge_destination="close",
        ),
        _conversation_node(
            "confirm_reschedule",
            "Read back the new appointment date/time to confirm. Tell them "
            "you're texting a confirmation now.",
            always_edge_destination="close",
        ),
        _conversation_node(
            "confirm_cancel",
            "Confirm the appointment has been cancelled.",
            always_edge_destination="close",
        ),
        {
            "id": "close",
            "type": "end",
            "instruction": {"type": "prompt", "text": "Thank the caller warmly and end the call."},
            "speak_during_execution": True,
        },
        _function_node(
            "transfer_to_human_fn",
            "transfer_to_human",
            always_edge_destination="transfer_call",
            global_condition=HUMAN_TRANSFER_GLOBAL_CONDITION,
        ),
        {
            "id": "transfer_call",
            "type": "transfer_call",
            "transfer_destination": {"type": "predefined", "number": "{{transfer_to}}"},
            "transfer_option": {"type": "cold_transfer"},
            "edge": _edge(
                "transfer_call__failed",
                "The transfer fails, is declined, or the line disconnects.",
                "close",
            ),
        },
    ]
    return nodes


def build_global_prompt(business: dict[str, Any]) -> str:
    hours = business.get("hours", {})
    hours_summary = "; ".join(f"{day} {window}" for day, window in hours.items())
    return GLOBAL_PROMPT_TEMPLATE.format(
        business_name=business["business_name"],
        service_area=business["service_area"],
        hours_summary=hours_summary,
    )


def _faq_hash(faq: list[dict[str, str]]) -> str:
    return hashlib.sha256(json.dumps(faq, sort_keys=True).encode("utf-8")).hexdigest()


def load_state(path: Path) -> dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def provision_knowledge_base(client: Retell, business: dict[str, Any], state: dict[str, Any]) -> str:
    faq = business.get("faq", [])
    current_hash = _faq_hash(faq)
    if state.get("knowledge_base_id") and state.get("knowledge_base_faq_hash") == current_hash:
        print(f"Knowledge base unchanged, reusing {state['knowledge_base_id']}")
        return state["knowledge_base_id"]

    if state.get("knowledge_base_id"):
        print(f"FAQ content changed, deleting old knowledge base {state['knowledge_base_id']}")
        client.knowledge_base.delete(state["knowledge_base_id"])

    texts = [{"title": item["question"], "text": item["answer"]} for item in faq]
    kb = client.knowledge_base.create(knowledge_base_name="hvac-receptionist-faq", knowledge_base_texts=texts)
    print(f"Created knowledge base {kb.knowledge_base_id}")
    state["knowledge_base_id"] = kb.knowledge_base_id
    state["knowledge_base_faq_hash"] = current_hash
    return kb.knowledge_base_id


def provision_conversation_flow(
    client: Retell, business: dict[str, Any], tools: list[dict[str, Any]], kb_id: str, state: dict[str, Any]
) -> str:
    params: dict[str, Any] = {
        "model_choice": {"type": "cascading", "model": "gpt-4.1-mini"},
        "start_speaker": "agent",
        "start_node_id": "greet",
        "global_prompt": build_global_prompt(business),
        "nodes": build_nodes(business),
        "tools": tools,
        "knowledge_base_ids": [kb_id],
        "default_dynamic_variables": {
            "transfer_to": business["on_call_transfer_number"],
            "business_name": business["business_name"],
        },
    }

    flow_id = state.get("conversation_flow_id")
    if flow_id:
        flow = client.conversation_flow.update(flow_id, **params)
        print(f"Updated conversation flow {flow.conversation_flow_id}")
    else:
        flow = client.conversation_flow.create(**params)
        print(f"Created conversation flow {flow.conversation_flow_id}")
    state["conversation_flow_id"] = flow.conversation_flow_id
    return flow.conversation_flow_id


def provision_agent(
    client: Retell, flow_id: str, voice_id: str, state: dict[str, Any], backend_base_url: str
) -> str:
    params: dict[str, Any] = {
        "response_engine": {"type": "conversation-flow", "conversation_flow_id": flow_id},
        "voice_id": voice_id,
        "agent_name": "HVAC Receptionist",
        "data_storage_setting": "everything",
        "webhook_url": backend_base_url.rstrip("/") + "/webhooks/retell-post-call",
        "handbook_config": {"ai_disclosure": True},
        "guardrail_config": {
            "input_topics": ["platform_integrity_jailbreaking"],
            "output_topics": [
                "harassment",
                "self_harm",
                "sexual_exploitation",
                "violence",
                "defense_and_national_security",
                "illicit_and_harmful_activity",
                "gambling",
                "regulated_professional_advice",
                "child_safety_and_exploitation",
            ],
        },
    }

    agent_id = state.get("agent_id")
    if agent_id:
        agent = client.agent.update(agent_id, **params)
        print(f"Updated agent {agent.agent_id}")
    else:
        agent = client.agent.create(**params)
        print(f"Created agent {agent.agent_id}")
    state["agent_id"] = agent.agent_id
    return agent.agent_id


def main() -> None:
    settings = get_settings()
    business = get_business_config()

    if not settings.retell_api_key:
        raise SystemExit("RETELL_API_KEY is not set in .env — cannot provision the agent.")
    if not settings.retell_voice_id:
        raise SystemExit(
            "RETELL_VOICE_ID is not set in .env. Pick a voice id from the Retell "
            "dashboard's Voice Library (or `retell.voice.list()`) and set it before "
            "running this script — there is no API-derivable default."
        )

    client = Retell(api_key=settings.retell_api_key)
    state = load_state(settings.retell_state_path)

    kb_id = provision_knowledge_base(client, business, state)
    save_state(settings.retell_state_path, state)

    tools = build_tools(settings.backend_base_url)
    flow_id = provision_conversation_flow(client, business, tools, kb_id, state)
    save_state(settings.retell_state_path, state)

    agent_id = provision_agent(client, flow_id, settings.retell_voice_id, state, settings.backend_base_url)
    save_state(settings.retell_state_path, state)

    print(f"\nDone. agent_id={agent_id} conversation_flow_id={flow_id} knowledge_base_id={kb_id}")
    print(f"State cached in {settings.retell_state_path} for idempotent reruns.")
    print(
        "\nRemaining dashboard-only steps: assign a phone number to this agent "
        "(Dashboard > Phone Numbers), and run it through LLM Playground / "
        "Web Call testing before go-live."
    )


if __name__ == "__main__":
    main()
