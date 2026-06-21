# Aireceptionist

AI voice receptionist backend for an HVAC company, built on **Retell AI**
(Conversation Flow agent). This repo is the webhook backend: Custom Function
endpoints, post-call pipeline, DB schema, and the Retell agent provisioning
script. The Retell dashboard/API config (nodes, transitions, Knowledge Base)
is provisioned from `scripts/provision_retell_agent.py` (added in M3).

## Status: M2 — all Custom Functions + Postgres + Google Calendar

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
- pytest suite (21 tests) covering happy path, bad/missing signature,
  idempotent double-call, and not-found cases for every endpoint, using an
  in-memory fake Google Calendar client and a rolled-back DB transaction per
  test (no real Google credentials needed to run tests).

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

- **M3** — `scripts/provision_retell_agent.py`: flow, nodes, function
  bindings, Node KB.
- **M4** — Post-call pipeline: Post-Call Analysis, Twilio SMS, Jobber CRM
  upsert, call/transcript logging.
- **M5** — Simulation test suite (`retell_sim_tests/`), Agent Guardrails,
  AI-disclosure + two-party-consent recording disclosure.
- **M6** — Web/Phone Call Testing, deploy notes.
