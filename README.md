# Aireceptionist

AI voice receptionist backend for an HVAC company, built on **Retell AI**
(Conversation Flow agent). This repo is the webhook backend: Custom Function
endpoints, post-call pipeline, DB schema, and the Retell agent provisioning
script. The Retell dashboard/API config (nodes, transitions, Knowledge Base)
is provisioned from `scripts/provision_retell_agent.py` (added in M3).

## Status: M1 — backend scaffold

- FastAPI app with one Custom Function endpoint stub: `check_availability`
  (returns two fake slots; real Google Calendar integration lands in M2).
- `X-Retell-Signature` verification on every webhook request (401 on
  missing/invalid signature) via Retell's Python SDK.
- Postgres schema (leads, appointments, call_logs, transcripts) + Alembic
  migrations.
- `config/business.yaml` holds editable business info (name, hours, service
  area, transfer number, FAQ, greeting/gas-safety scripts) — **edit the
  placeholders before go-live**.
- pytest suite covering happy path, bad signature, missing signature, and
  idempotent double-call for the stub endpoint.

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

- **M2** — Remaining Custom Function endpoints (`book_visit`,
  `reschedule_visit`, `cancel_visit`, `capture_lead`, `flag_emergency`,
  `transfer_to_human`) + Google Calendar integration.
- **M3** — `scripts/provision_retell_agent.py`: flow, nodes, function
  bindings, Node KB.
- **M4** — Post-call pipeline: Post-Call Analysis, Twilio SMS, Jobber CRM
  upsert, call/transcript logging.
- **M5** — Simulation test suite (`retell_sim_tests/`), Agent Guardrails,
  AI-disclosure + two-party-consent recording disclosure.
- **M6** — Web/Phone Call Testing, deploy notes.
