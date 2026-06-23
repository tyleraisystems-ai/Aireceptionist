import json
from typing import Callable

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import IdempotencyKey


def run_idempotent(db: Session, key: str, compute: Callable[[], dict]) -> tuple[dict, bool]:
    """Return (result, was_cached).

    Looks up `key` first; if present, returns the stored result without
    calling `compute`. Otherwise runs `compute` (which may stage its own
    writes on `db`), stores the result under `key`, and commits both
    atomically. If a concurrent request commits the same key first, this
    falls back to the now-existing cached result instead of erroring.
    """
    existing = db.get(IdempotencyKey, key)
    if existing is not None:
        return json.loads(existing.response_json), True

    result = compute()
    db.add(IdempotencyKey(key=key, response_json=json.dumps(result)))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.get(IdempotencyKey, key)
        if existing is not None:
            return json.loads(existing.response_json), True
        raise
    return result, False
