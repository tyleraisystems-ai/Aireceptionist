import json

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import FunctionCallLog


def get_cached_result(db: Session, *, call_id: str, function_name: str) -> dict | None:
    log = (
        db.query(FunctionCallLog)
        .filter_by(call_id=call_id, function_name=function_name)
        .one_or_none()
    )
    return json.loads(log.result_json) if log else None


def cache_result(db: Session, *, call_id: str, function_name: str, result: dict) -> None:
    db.add(FunctionCallLog(call_id=call_id, function_name=function_name, result_json=json.dumps(result)))
    try:
        db.commit()
    except IntegrityError:
        # Lost a race with a concurrent retry; the other request's cached
        # result is now the source of truth, so just discard ours.
        db.rollback()
