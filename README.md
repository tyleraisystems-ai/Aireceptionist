# Aireceptionist

AI voice receptionist backend for an HVAC company, built on **Retell AI**
(Conversation Flow agent). This repo is the webhook backend: Custom Function
endpoints, post-call pipeline, DB schema, and the Retell agent provisioning
script. The Retell dashboard/API config (nodes, transitions, Knowledge Base)
is provisioned from `scripts/provision_retell_agent.py` (added in M3).

## Status: M3 — Retell agent/flow provisioning script

- All 7 Custom Function endpoints are live and DB-backed: `check_availability`,
  `book_visit`, `reschedule_visit`, `cancel_visit` (all backed by Google
  Calendar), plus `capture_lead`, `flag_emergency`, `transfer_to_human`.
- `X-Retell-Signature` verification on every webhook request (401 on
  missing/invalid signature) via Retell's Python SDK.
- Idempotency: each mutating function caches its result keyed on Retell's
  `call_id` + function name (`function_call_logs` table), so Retell's retries
  (up to 2x) replay the cached result instead of double-booking/double-leading.
- Postgres schema (leads, appointments, call_logs, transcripts,
  function_call_logs) + Alembic migrations.
- `config/business.yaml` holds editable business info (name, hours, service
  area, transfer number, FAQ, greeting/gas-safety scripts) — **edit the
  placeholders before go-live**.
- `scripts/provision_retell_agent.py` provisions the Retell Knowledge Base
  (from `config/business.yaml`'s `faq`), Conversation Flow (22 nodes — see
  below), and Agent via the Retell API. Idempotent: resource IDs are cached
  in a local, gitignored `.retell_state.json`, so reruns `update()` existing
  resources instead of creating duplicates. Requires `RETELL_API_KEY`,
  `RETELL_VOICE_ID`, and `BACKEND_BASE_URL` set in `.env`. Run with
  `python -m scripts.provision_retell_agent`.
  - **Node count vs. spec**: the original spec described the flow as "7
    nodes + 1 emergency-end node." Retell's Conversation Flow graph requires
    a separate node per function call, per branching outcome, and per
    terminal state, so a fully wired implementation of every spec'd
    capability (book/reschedule/cancel, urgent triage, gas safety, FAQ via
    KB, transfer-to-human) comes out to 22 nodes. These map onto the
    original 7 conceptual stages: **Greet** (`greet`) → **Gas-safety**
    (`gas_safety`, `gas_emergency_end`) → **Triage** (`triage`) →
    **Collect** (`collect_urgent`, `collect_routine`, plus
    `manage_existing` for callers with an existing appointment) →
    **Book-or-flag** (`flag_emergency_fn`, `check_availability_fn`,
    `offer_times`, `book_visit_fn`, `capture_lead_fn`,
    `reschedule_visit_fn`, `cancel_visit_fn`) → **Confirm**
    (`confirm_urgent`, `confirm_routine`, `confirm_no_match`,
    `confirm_reschedule`, `confirm_cancel`) → **Close** (`close`). Two
    globally-reachable nodes (`global_node_setting`) sit outside that
    sequence: gas-safety can fire from anywhere a caller mentions gas, and
    `transfer_to_human_fn` → `transfer_call` can fire from anywhere the
    caller is upset or asks for a person.
  - **Known quirk**: the spec's urgent path is "capture_lead + flag_emergency."
    `flag_emergency`'s endpoint already creates its own `Lead` row, so
    chaining both would create two lead rows per urgent call. The flow only
    calls `flag_emergency_fn` for the urgent path; `capture_lead_fn` is used
    solely for the "no offered time worked" routine fallback.
  - **Dashboard-only steps** (cannot be done via API): picking/previewing a
    `voice_id` (Dashboard > Voice Library, or `retell.voice.list()` with a
    real API key — set the result as `RETELL_VOICE_ID`); buying/assigning a
    phone number to the provisioned agent; final review of the AI-disclosure
    and two-party-consent recording wording before go-live; LLM Playground /
    Web Call / Phone Call testing (M6).
- pytest suite (30 tests) covering happy path, bad/missing signature,
  idempotent double-call, and not-found cases for every endpoint, using an
  in-memory fake Google Calendar client and a rolled-back DB transaction per
  test (no real Google credentials needed to run tests) — plus tests for the
  provisioning script's node-graph construction and create/update/idempotency
  logic against a fake Retell client (no real Retell credentials needed).

## Setup

```bash
uv venv .venv && source .venv/bin/activate
uv pip install -e ".[dev]"
cp .env.example .env   # fill in RETELL_API_KEY at minimum
```

### Database

```bash
# create a local Postgres role/db matching DATABASE_URL in .env
sudo -u postgres psql -c "CREATE USER aireceptionist WITH PASSWORD 'aireceptionist';"
sudo -u postgres psql -c "CREATE DATABASE aireceptionist OWNER aireceptionist;"
alembic upgrade head
```

### Run locally

```bash
uvicorn app.main:app --reload --port 8000
curl localhost:8000/health
```

### Expose to Retell via ngrok (for wiring a real Custom Function in the dashboard)

```bash
ngrok http 8000
# In the Retell dashboard, set the check_availability Custom Function's
# webhook URL to https://<ngrok-id>.ngrok-free.app/functions/check-availability
```

### Tests

```bash
pytest -v
```

## Roadmap

- **M4** — Post-call pipeline: Post-Call Analysis, Twilio SMS, Jobber CRM
  upsert, call/transcript logging.
- **M5** — Simulation test suite (`retell_sim_tests/`), Agent Guardrails,
  AI-disclosure + two-party-consent recording disclosure.
- **M6** — Web/Phone Call Testing, deploy notes.
