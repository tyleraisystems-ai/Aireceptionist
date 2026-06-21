# Deploy & go-live checklist (M6)

## 1. Build & run the backend

```bash
docker build -t aireceptionist .
docker run -p 8000:8000 --env-file .env aireceptionist
```

There's no `docker-compose.yml` for Postgres here — point `DATABASE_URL` at
whatever Postgres instance you're running in production (a managed instance
is recommended; this app makes no assumptions about where it lives).

No process manager config (systemd unit, gunicorn) is included beyond the
Dockerfile's `uvicorn` entrypoint — add a reverse proxy (nginx/Caddy) or your
platform's equivalent in front of it for TLS termination, since Retell will
be POSTing to this service over the public internet.

## 2. Environment variables

All required at runtime, see `.env.example` for the full annotated list:

- `RETELL_API_KEY` — also used to verify `X-Retell-Signature` on every
  inbound webhook request.
- `DATABASE_URL` — Postgres connection string (run `alembic upgrade head`
  against it before first start).
- `GOOGLE_CALENDAR_CREDENTIALS_JSON`, `GOOGLE_CALENDAR_ID` — service account
  key (path or raw JSON) + the calendar it's been shared with (Editor).
- `JOBBER_CLIENT_ID`, `JOBBER_CLIENT_SECRET`, `JOBBER_REFRESH_TOKEN` — Jobber
  CRM OAuth2 credentials.
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER` — SMS
  confirmations/alerts.
- `BACKEND_BASE_URL` — **must be your real public domain in production**,
  not an ngrok URL. This is baked into the Agent's `webhook_url` and every
  Custom Function tool's URL at provisioning time (see step 4).
- `RETELL_VOICE_ID` — picked via Dashboard Voice Library or
  `retell.voice.list()`.

## 3. Database

```bash
alembic upgrade head
```

Run this against the production database before starting the app, and again
after pulling any future migration.

## 4. Provision/update the Retell agent for production

Once `BACKEND_BASE_URL` in `.env` points at your real domain (not ngrok),
rerun:

```bash
python -m scripts.provision_retell_agent
```

This is idempotent (see `.retell_state.json`) — it `update()`s the existing
Knowledge Base, Conversation Flow, and Agent in place rather than creating
duplicates, but it rewrites every Custom Function tool URL and the Agent's
`webhook_url` to the current `BACKEND_BASE_URL`. **This is the one step that
must be re-run any time the backend's public URL changes** (e.g. moving off
ngrok at go-live).

If you ever need a clean re-provision instead of an update (e.g. testing a
from-scratch setup), delete `.retell_state.json` first.

## 5. Manual smoke tests

- **Web call** (no phone number needed):
  ```bash
  python -m scripts.create_web_call
  python -m http.server 8001   # in the repo root, separate terminal
  ```
  Open the printed `http://localhost:8001/web_test/index.html?token=...` URL,
  click "Start Call", and talk to the agent. Requires microphone permission
  (browser secure-context rules mean this won't work over `file://`).

- **Phone call** — requires a real Retell phone number already purchased and
  bound to the agent first (Dashboard > Phone Numbers, or
  `client.phone_number.create(inbound_agents=[...])` — a real, billable
  action, intentionally not automated by any script here):
  ```bash
  python -m scripts.create_test_phone_call --from +1555... --to +1555...
  ```

- **Simulation suite** (scripted scenarios, no phone number needed):
  ```bash
  python -m scripts.run_simulation_tests
  ```

## 6. Go-live checklist (dashboard-only steps, scattered across M3–M6)

These can't be done via the provisioning script and need a one-time manual
pass before taking real traffic:

- [ ] Pick and set `RETELL_VOICE_ID` (Dashboard Voice Library or
  `retell.voice.list()`).
- [ ] Edit the placeholders in `config/business.yaml` (business name, hours,
  service area, transfer number, FAQ, greeting/gas-safety scripts).
- [ ] Purchase and bind a real phone number to the agent (Dashboard > Phone
  Numbers, or `client.phone_number.create(inbound_agents=[agent_id])`).
- [ ] Final legal/compliance review of the AI-disclosure and
  two-party-consent recording wording in `greeting_script` for your
  jurisdiction — the agent's recording-objection handling
  (`scripts/provision_retell_agent.py`'s `HUMAN_TRANSFER_GLOBAL_CONDITION`)
  assumes that wording is already correct.
- [ ] Run `python -m scripts.run_simulation_tests` and confirm all scenarios
  pass against your configured Evaluation Metrics.
- [ ] Run the web call smoke test (step 5) end-to-end at least once.
- [ ] Confirm `BACKEND_BASE_URL` is the real production domain and rerun
  `provision_retell_agent` (step 4) if it changed since the last run.
- [ ] Place one real test phone call (step 5) once a number is bound.
