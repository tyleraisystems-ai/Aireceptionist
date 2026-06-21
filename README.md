# Aireceptionist

AI voice receptionist backend for an HVAC company, built on **Retell AI**
(Conversation Flow agent). This repo is the webhook backend: Custom Function
endpoints, post-call pipeline, DB schema, and the Retell agent provisioning
script. The Retell dashboard/API config (nodes, transitions, Knowledge Base)
is provisioned from `scripts/provision_retell_agent.py` (added in M3).

## Status: M6 — Web/phone call testing, deploy notes

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
  below), and Agent via the Retell API. The Agent's `webhook_url` is set to
  `<BACKEND_BASE_URL>/webhooks/retell-post-call` so Retell delivers
  `call_started`/`call_ended`/`call_analyzed` events to the M4 post-call
  pipeline below. Idempotent: resource IDs are cached in a local, gitignored
  `.retell_state.json`, so reruns `update()` existing resources instead of
  creating duplicates. Requires `RETELL_API_KEY`, `RETELL_VOICE_ID`, and
  `BACKEND_BASE_URL` set in `.env`. Run with
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
- pytest suite (42 tests) covering happy path, bad/missing signature,
  idempotent double-call, and not-found cases for every endpoint, using an
  in-memory fake Google Calendar client and a rolled-back DB transaction per
  test (no real Google credentials needed to run tests) — plus tests for the
  provisioning script's node-graph construction and create/update/idempotency
  logic against a fake Retell client, and for the simulation test runner's
  provisioning/polling/reporting logic against a fake Retell `tests` client
  (no real Retell credentials needed for any of it).
- `POST /webhooks/retell-post-call` (signature-verified, same scheme as the
  Custom Function endpoints) handles Retell's three post-call webhook
  events, all delivered to this one configured `webhook_url`:
  - `call_started` — upserts a `call_logs` row with `caller_number` +
    `started_at`.
  - `call_ended` — stores `ended_at` and the raw transcript.
  - `call_analyzed` — the side-effecting event. Looks up the caller's most
    recent `Lead` by phone number (preferred over re-parsing Retell's
    LLM-extracted `call_analysis.custom_analysis_data`, since our own
    Custom Function endpoints already wrote authoritative lead/appointment
    data during the live call), stores the transcript + analysis JSON,
    sends a Twilio SMS confirmation to the caller, sends an urgent-lead
    alert SMS to `business.yaml`'s `on_call_transfer_number` when the
    matched lead is `URGENT`, and upserts a Jobber CRM Client record (name,
    phone, address). **No CRM/SMS side effects happen during the live call**
    — they're all deferred to this post-call webhook, off the latency path.
  - Idempotent: a `post_call_processed` flag on `call_logs` guards against
    Retell redelivering `call_analyzed` and double-sending SMS / double-
    upserting the CRM record.
  - **Jobber scope**: deliberately limited to a Client upsert (search-by-
    phone, create-or-update name/address), not full Job/Request/Quote
    creation — matching the spec's literal "Jobber CRM upsert" wording
    rather than expanding scope.
  - Twilio and Jobber are both called via direct `httpx` requests (no
    `twilio` SDK dependency) following the same constructor-takes-`Settings`
    + module-level DI factory pattern as `GoogleCalendarClient`, so tests
    swap in `FakeTwilioClient`/`FakeJobberClient` doubles with no network
    access required.
- **Simulation test suite** (`retell_sim_tests/scenarios.py` +
  `scripts/run_simulation_tests.py`): 9 scenarios run as Retell Test Case
  Definitions against the provisioned conversation flow via Retell's
  `client.tests.*` batch-test API — routine booking, urgent no-heat
  emergency, gas-smell immediate safety response, reschedule, cancel, FAQ
  pricing (never quotes an exact price), explicit human-transfer request,
  recording-objection routes to a human, and the no-offered-time → lead
  capture fallback. Each scenario mocks its Custom Function calls
  (`tool_mocks`) so a run doesn't need a publicly reachable backend.
  Idempotent the same way as `provision_retell_agent.py`: test case
  definition IDs are cached in `.retell_state.json` and updated in place on
  reruns. Run with `python -m scripts.run_simulation_tests` after
  `provision_retell_agent` (requires a live `RETELL_API_KEY` and an account
  with the metric names in `DEFAULT_METRICS` configured in the dashboard's
  Evaluation Metrics — adjust if yours differ).
- **Agent Guardrails**: `guardrail_config.output_topics` now covers the
  full set of prohibited-topic categories the API exposes (added
  `defense_and_national_security`, `gambling`, `child_safety_and_exploitation`
  to the ones already set in M3).
- **Recording consent**: the global prompt and the human-transfer condition
  now explicitly handle a caller objecting to or declining the call being
  recorded — the agent doesn't argue, it offers an immediate transfer to a
  human, since recording can't be toggled off mid-call via the API. The
  existing `greeting_script` disclosure (`config/business.yaml`) plus this
  objection-handling path is the AI-disclosure/two-party-consent behavior;
  final wording sign-off for your jurisdiction is still a manual step (see
  "Dashboard-only steps" above).
- **Web/phone call testing tooling**:
  - `scripts/create_web_call.py` creates a Retell web call session against
    the provisioned agent (cached `agent_id` from `.retell_state.json`) and
    prints an access token plus a ready-to-open URL for
    `web_test/index.html`.
  - `web_test/index.html` is a dependency-free static page (loads
    `retell-client-js-sdk` from the unpkg CDN, no Node/build tooling) with
    Start/Stop buttons and a live transcript, for manually talking to the
    agent end-to-end in a browser. Must be served over `http://` (e.g.
    `python -m http.server 8001`), not opened via `file://`, since
    microphone access requires a secure context.
  - `scripts/create_test_phone_call.py` places an outbound test phone call
    from a Retell-owned number to a destination you specify
    (`--from`/`--to`, E.164). Requires a phone number already purchased and
    bound to the agent first — a real, billable action (Dashboard > Phone
    Numbers, or `client.phone_number.create(inbound_agents=[...])`),
    intentionally not automated by any script here.
- **Deploy notes**: see `DEPLOY.md` for the production Dockerfile, the full
  environment-variable checklist, running `alembic upgrade head` against the
  production DB, re-running `provision_retell_agent` once `BACKEND_BASE_URL`
  points at a real domain instead of an ngrok tunnel (this rewrites every
  Custom Function tool URL and the Agent's `webhook_url`), and a
  consolidated go-live checklist pulling together every dashboard-only step
  scattered across M3–M6 (voice_id pick, phone number purchase/binding,
  compliance wording sign-off, simulation suite, web/phone call smoke
  tests).

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

### Deploying

See `DEPLOY.md` for the production Dockerfile, environment-variable
checklist, and go-live checklist.
