# Aireceptionist

Open-source AI receptionist for HVAC firms — automates calls/chats for service
inquiries, emergencies, maintenance booking, quotes, and dispatch. Integrates
calendars, CRM, and dispatching. LLM-powered.

## Repo state
This repo is currently a blank slate (README only). No production app code
exists yet.

## demo/ — learning sandbox, not production code
`demo/` contains a standalone FastAPI webhook backend + n8n workflow, built
as a teaching example for context engineering and orchestration patterns.
It is intentionally decoupled from the real product — do not wire it into
production CRM/dispatch logic. Treat it as disposable reference material.

- `demo/app/` — FastAPI app
- `demo/requirements.txt` — Python deps
- Run: `uvicorn app.main:app --reload` from `demo/`

## Conventions
- Work on feature branches, never commit directly to `main`.
