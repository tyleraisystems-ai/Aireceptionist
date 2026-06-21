"""Tests for the simulation test runner's pure logic, against a fake Retell
tests client (no real Retell credentials or network access needed).
"""

from types import SimpleNamespace

from retell_sim_tests.scenarios import SCENARIOS
from scripts.run_simulation_tests import (
    poll_batch_test,
    print_report,
    provision_test_case_definitions,
    run_batch_test,
)


class FakeTestsResource:
    def __init__(self):
        self.create_calls = []
        self.update_calls = []
        self._next_definition_id = 1
        self.batches: dict[str, SimpleNamespace] = {}
        self.runs: dict[str, list[SimpleNamespace]] = {}

    def create_test_case_definition(self, **params):
        self.create_calls.append(params)
        definition_id = f"def_{self._next_definition_id}"
        self._next_definition_id += 1
        return SimpleNamespace(test_case_definition_id=definition_id)

    def update_test_case_definition(self, definition_id, **params):
        self.update_calls.append((definition_id, params))
        return SimpleNamespace(test_case_definition_id=definition_id)

    def create_batch_test(self, **params):
        batch_id = f"batch_{len(self.batches) + 1}"
        self.batches[batch_id] = SimpleNamespace(
            test_case_batch_job_id=batch_id, status="complete", pass_count=1, fail_count=0, error_count=0
        )
        return self.batches[batch_id]

    def get_batch_test(self, batch_id):
        return self.batches[batch_id]

    def list_test_runs(self, batch_id, **kwargs):
        items = self.runs.get(batch_id, [])
        return SimpleNamespace(items=items, has_more=False, pagination_key=None)


class FakeClient:
    def __init__(self):
        self.tests = FakeTestsResource()


def test_provision_test_case_definitions_creates_then_updates():
    client = FakeClient()
    state: dict = {}

    ids_1 = provision_test_case_definitions(client, "flow_1", state)
    assert len(ids_1) == len(SCENARIOS)
    assert len(client.tests.create_calls) == len(SCENARIOS)
    assert len(client.tests.update_calls) == 0
    assert set(state["sim_test_case_ids"]) == {s["name"] for s in SCENARIOS}

    ids_2 = provision_test_case_definitions(client, "flow_1", state)
    assert ids_2 == ids_1
    assert len(client.tests.create_calls) == len(SCENARIOS)  # not recreated
    assert len(client.tests.update_calls) == len(SCENARIOS)  # updated instead


def test_provision_test_case_definitions_uses_conversation_flow_response_engine():
    client = FakeClient()
    state: dict = {}
    provision_test_case_definitions(client, "flow_x", state)
    for params in client.tests.create_calls:
        assert params["response_engine"] == {"type": "conversation-flow", "conversation_flow_id": "flow_x"}


def test_run_batch_test_passes_through_definition_ids():
    client = FakeClient()
    batch = run_batch_test(client, "flow_1", ["def_1", "def_2"])
    assert batch.test_case_batch_job_id == "batch_1"


def test_poll_batch_test_returns_completed_batch():
    client = FakeClient()
    batch = run_batch_test(client, "flow_1", ["def_1"])
    completed = poll_batch_test(client, batch.test_case_batch_job_id)
    assert completed.status == "complete"


def test_print_report_detects_failures(capsys):
    client = FakeClient()
    batch = run_batch_test(client, "flow_1", ["def_1"])
    client.tests.runs[batch.test_case_batch_job_id] = [
        SimpleNamespace(
            status="pass",
            test_case_definition_snapshot=SimpleNamespace(name="routine_booking_happy_path"),
            result_explanation=None,
        ),
        SimpleNamespace(
            status="fail",
            test_case_definition_snapshot=SimpleNamespace(name="gas_smell_immediate_safety_response"),
            result_explanation="Agent offered to book an appointment instead of ending the call.",
        ),
    ]

    all_passed = print_report(client, batch.test_case_batch_job_id)

    assert all_passed is False
    output = capsys.readouterr().out
    assert "[PASS] routine_booking_happy_path" in output
    assert "[FAIL] gas_smell_immediate_safety_response" in output
    assert "offered to book an appointment" in output


def test_print_report_all_pass():
    client = FakeClient()
    batch = run_batch_test(client, "flow_1", ["def_1"])
    client.tests.runs[batch.test_case_batch_job_id] = [
        SimpleNamespace(
            status="pass", test_case_definition_snapshot=SimpleNamespace(name="s1"), result_explanation=None
        )
    ]
    assert print_report(client, batch.test_case_batch_job_id) is True
