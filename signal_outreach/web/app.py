from fastapi import FastAPI
from sqlmodel import Session, text

from ..config import settings
from ..db import engine, init_db

app = FastAPI(title="Signal Outreach")

REQUIRED_ENV_VARS = [
    "anthropic_api_key",
    "apify_api_token",
    "zerobounce_api_key",
    "smartlead_api_key",
]


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/healthz")
def healthz() -> dict:
    db_ok = True
    try:
        with Session(engine) as session:
            session.exec(text("SELECT 1"))
    except Exception:
        db_ok = False

    missing_env = [name for name in REQUIRED_ENV_VARS if not getattr(settings, name)]

    return {
        "status": "ok" if db_ok else "degraded",
        "db_ok": db_ok,
        "missing_env_vars": missing_env,
    }
