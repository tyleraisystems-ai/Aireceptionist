"""Run the Retell Conversation Flow simulation test suite (M5).

Creates (or updates, on rerun) a Retell Test Case Definition per scenario in
retell_sim_tests/scenarios.py against the already-provisioned conversation
flow, runs them as a single batch test, polls until the batch completes, and
prints a pass/fail/error report per scenario.

Idempotency: test case definition IDs are cached in the same gitignored
state file used by scripts/provision_retell_agent.py (.retell_state.json,
under the "sim_test_case_ids" key), so reruns call update() on existing
definitions instead of creating duplicates each time.

Requires scripts/provision_retell_agent.py to have been run first (a
conversation_flow_id must already be cached in state).

Usage:
    python -m scripts.run_simulation_tests
"""
from __future__ import annotations

import sys
import time
from typing import Any

from retell import Retell

from app.core.settings import get_settings
from retell_sim_tests.scenarios import SCENARIOS
from scripts.provision_retell_agent import load_state, save_state

POLL_INTERVAL_SECONDS = 5
POLL_TIMEOUT_SECONDS = 600


def provision_test_case_definitions(client: Retell, conversation_flow_id: str, state: dict[str, Any]) -> list[str]:
    cached: dict[str, str] = state.setdefault("sim_test_case_ids", {})
    response_engine = {"type": "conversation-flow", "conversation_flow_id": conversation_flow_id}

    ids = []
    for scenario in SCENARIOS:
        params = {
            "name": scenario["name"],
            "user_prompt": scenario["user_prompt"],
            "metrics": scenario["metrics"],
            "response_engine": response_engine,
            "tool_mocks": scenario.get("tool_mocks", []),
        }
        existing_id = cached.get(scenario["name"])
        if existing_id:
            definition = client.tests.update_test_case_definition(existing_id, **params)
        else:
            definition = client.tests.create_test_case_definition(**params)
        cached[scenario["name"]] = definition.test_case_definition_id
        ids.append(definition.test_case_definition_id)
    return ids


def run_batch_test(client: Retell, conversation_flow_id: str, test_case_definition_ids: list[str]) -> Any:
    return client.tests.create_batch_test(
        response_engine={"type": "conversation-flow", "conversation_flow_id": conversation_flow_id},
        test_case_definition_ids=test_case_definition_ids,
    )


def poll_batch_test(client: Retell, batch_job_id: str) -> Any:
    deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
    while True:
        batch = client.tests.get_batch_test(batch_job_id)
        if batch.status == "complete":
            return batch
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Batch test {batch_job_id} did not complete within {POLL_TIMEOUT_SECONDS}s")
        time.sleep(POLL_INTERVAL_SECONDS)


def print_report(client: Retell, batch_job_id: str) -> bool:
    all_passed = True
    pagination_key = None
    while True:
        kwargs = {"pagination_key": pagination_key} if pagination_key else {}
        page = client.tests.list_test_runs(batch_job_id, **kwargs)
        for run in page.items or []:
            status_label = run.status.upper()
            name = run.test_case_definition_snapshot.name
            print(f"[{status_label}] {name}")
            if run.status != "pass":
                all_passed = False
                if run.result_explanation:
                    print(f"    {run.result_explanation}")
        if not page.has_more:
            break
        pagination_key = page.pagination_key
    return all_passed


def main() -> None:
    settings = get_settings()
    state = load_state(settings.retell_state_path)
    conversation_flow_id = state.get("conversation_flow_id")
    if not conversation_flow_id:
        raise SystemExit(
            "No conversation_flow_id in .retell_state.json — run "
            "`python -m scripts.provision_retell_agent` first."
        )

    client = Retell(api_key=settings.retell_api_key)

    test_case_ids = provision_test_case_definitions(client, conversation_flow_id, state)
    save_state(settings.retell_state_path, state)

    print(f"Running batch test against {len(test_case_ids)} scenarios...")
    batch = run_batch_test(client, conversation_flow_id, test_case_ids)
    batch = poll_batch_test(client, batch.test_case_batch_job_id)
    print(f"\nBatch test complete: {batch.pass_count} passed, {batch.fail_count} failed, {batch.error_count} errored\n")

    all_passed = print_report(client, batch.test_case_batch_job_id)
    if not all_passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
