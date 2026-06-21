"""Tests for the Retell provisioning script's pure logic.

These run with no real Retell credentials: node-graph construction is tested
directly, and the create-vs-update / KB recreate-on-change logic is tested
against a small fake client standing in for the Retell SDK.
"""

from types import SimpleNamespace

from app.core.business_config import get_business_config
from scripts.provision_retell_agent import (
    FUNCTION_TOOL_DEFS,
    build_global_prompt,
    build_nodes,
    build_tools,
    provision_agent,
    provision_conversation_flow,
    provision_knowledge_base,
)


def _all_node_ids(nodes: list[dict]) -> set[str]:
    return {n["id"] for n in nodes}


def test_build_nodes_edges_reference_real_nodes():
    business = get_business_config()
    nodes = build_nodes(business)
    node_ids = _all_node_ids(nodes)

    assert len(node_ids) == len(nodes)  # no duplicate ids

    for node in nodes:
        for edge in node.get("edges", []) or []:
            assert edge["destination_node_id"] in node_ids
        for key in ("else_edge", "always_edge"):
            edge = node.get(key)
            if edge:
                assert edge["destination_node_id"] in node_ids
        if node["type"] == "transfer_call":
            assert node["edge"]["destination_node_id"] in node_ids


def test_build_nodes_has_one_start_and_two_end_nodes():
    nodes = build_nodes(get_business_config())
    end_nodes = [n for n in nodes if n["type"] == "end"]
    assert {n["id"] for n in end_nodes} == {"gas_emergency_end", "close"}


def test_gas_safety_and_human_transfer_are_globally_reachable():
    nodes = build_nodes(get_business_config())
    by_id = {n["id"]: n for n in nodes}
    assert "global_node_setting" in by_id["gas_safety"]
    assert "global_node_setting" in by_id["transfer_to_human_fn"]


def test_build_tools_covers_all_seven_custom_functions():
    tools = build_tools("http://localhost:8000")
    names = {t["name"] for t in tools}
    assert names == {spec["name"] for spec in FUNCTION_TOOL_DEFS}
    for tool in tools:
        assert tool["url"].startswith("http://localhost:8000/functions/")
        assert tool["type"] == "custom"


def test_build_global_prompt_includes_business_name_and_hard_rules():
    prompt = build_global_prompt(get_business_config())
    assert "Acme HVAC" in prompt
    assert "Never quote an exact price" in prompt


class FakeKnowledgeBase:
    def __init__(self):
        self.created = []
        self.deleted = []

    def create(self, *, knowledge_base_name, knowledge_base_texts):
        kb_id = f"kb_{len(self.created)}"
        self.created.append((knowledge_base_name, knowledge_base_texts))
        return SimpleNamespace(knowledge_base_id=kb_id)

    def delete(self, knowledge_base_id):
        self.deleted.append(knowledge_base_id)


class FakeConversationFlow:
    def __init__(self):
        self.create_calls = []
        self.update_calls = []

    def create(self, **params):
        self.create_calls.append(params)
        return SimpleNamespace(conversation_flow_id="flow_1")

    def update(self, flow_id, **params):
        self.update_calls.append((flow_id, params))
        return SimpleNamespace(conversation_flow_id=flow_id)


class FakeAgent:
    def __init__(self):
        self.create_calls = []
        self.update_calls = []

    def create(self, **params):
        self.create_calls.append(params)
        return SimpleNamespace(agent_id="agent_1")

    def update(self, agent_id, **params):
        self.update_calls.append((agent_id, params))
        return SimpleNamespace(agent_id=agent_id)


class FakeClient:
    def __init__(self):
        self.knowledge_base = FakeKnowledgeBase()
        self.conversation_flow = FakeConversationFlow()
        self.agent = FakeAgent()


def test_provision_knowledge_base_creates_then_reuses_when_unchanged():
    client = FakeClient()
    business = get_business_config()
    state: dict = {}

    kb_id_1 = provision_knowledge_base(client, business, state)
    assert kb_id_1 == "kb_0"
    assert len(client.knowledge_base.created) == 1

    kb_id_2 = provision_knowledge_base(client, business, state)
    assert kb_id_2 == kb_id_1
    assert len(client.knowledge_base.created) == 1  # not recreated
    assert client.knowledge_base.deleted == []


def test_provision_knowledge_base_recreates_when_faq_changes():
    client = FakeClient()
    business = dict(get_business_config())
    state: dict = {}

    provision_knowledge_base(client, business, state)

    business["faq"] = business["faq"] + [{"question": "New?", "answer": "Yes."}]
    kb_id_2 = provision_knowledge_base(client, business, state)

    assert kb_id_2 == "kb_1"
    assert client.knowledge_base.deleted == ["kb_0"]


def test_provision_conversation_flow_creates_then_updates():
    client = FakeClient()
    business = get_business_config()
    tools = build_tools("http://localhost:8000")
    state: dict = {}

    flow_id_1 = provision_conversation_flow(client, business, tools, "kb_x", state)
    assert flow_id_1 == "flow_1"
    assert len(client.conversation_flow.create_calls) == 1
    assert len(client.conversation_flow.update_calls) == 0

    flow_id_2 = provision_conversation_flow(client, business, tools, "kb_x", state)
    assert flow_id_2 == flow_id_1
    assert len(client.conversation_flow.create_calls) == 1
    assert len(client.conversation_flow.update_calls) == 1


def test_provision_agent_creates_then_updates():
    client = FakeClient()
    state: dict = {}

    agent_id_1 = provision_agent(client, "flow_1", "voice_x", state, "http://localhost:8000")
    assert agent_id_1 == "agent_1"
    assert len(client.agent.create_calls) == 1
    assert client.agent.create_calls[0]["webhook_url"] == "http://localhost:8000/webhooks/retell-post-call"

    agent_id_2 = provision_agent(client, "flow_1", "voice_x", state, "http://localhost:8000")
    assert agent_id_2 == agent_id_1
    assert len(client.agent.update_calls) == 1
