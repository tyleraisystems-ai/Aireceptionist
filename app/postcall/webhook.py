import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.business_config import get_business_config
from app.core.retell_verify import verify_retell_signature
from app.db import crud
from app.db.session import get_db
from app.integrations.jobber import JobberClient, get_jobber_client
from app.integrations.twilio_sms import TwilioSmsClient, get_twilio_client
from app.postcall.schemas import PostCallWebhook

router = APIRouter()


def _ms_to_datetime(ms: int | None) -> datetime | None:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc) if ms is not None else None


@router.post("/webhooks/retell-post-call")
async def retell_post_call(
    body: bytes = Depends(verify_retell_signature),
    db: Session = Depends(get_db),
    twilio: TwilioSmsClient = Depends(get_twilio_client),
    jobber: JobberClient = Depends(get_jobber_client),
) -> dict:
    webhook = PostCallWebhook.model_validate_json(body)
    call = webhook.call

    if webhook.event == "call_started":
        crud.upsert_call_log_started(
            db,
            retell_call_id=call.call_id,
            caller_number=call.from_number,
            started_at=_ms_to_datetime(call.start_timestamp),
        )
    elif webhook.event == "call_ended":
        call_log = crud.upsert_call_log_started(
            db, retell_call_id=call.call_id, caller_number=call.from_number, started_at=None
        )
        crud.update_call_log_ended(
            db, call_log, ended_at=_ms_to_datetime(call.end_timestamp), transcript_text=call.transcript
        )
    elif webhook.event == "call_analyzed":
        _process_call_analyzed(db, call, twilio=twilio, jobber=jobber)

    return {"status": "ok"}


def _process_call_analyzed(db: Session, call, *, twilio: TwilioSmsClient, jobber: JobberClient) -> None:
    call_log = crud.upsert_call_log_started(
        db, retell_call_id=call.call_id, caller_number=call.from_number, started_at=None
    )
    if call_log.post_call_processed:
        return  # already handled this call_analyzed delivery; Retell may redeliver

    business = get_business_config()
    lead = crud.get_latest_lead_by_phone(db, call.from_number) if call.from_number else None

    analysis_json = json.dumps(call.call_analysis.model_dump()) if call.call_analysis else None
    crud.record_call_analysis(
        db,
        call_log,
        transcript_text=call.transcript,
        analysis_json=analysis_json,
        disposition=lead.disposition if lead else None,
        urgency=lead.urgency if lead else None,
        lead_id=lead.id if lead else None,
    )

    if call.from_number:
        twilio.send_sms(
            call.from_number,
            f"Thanks for calling {business['business_name']}! We've got your details "
            "and will follow up shortly. Reply to this text if anything changes.",
        )

    if lead and lead.urgency == "URGENT":
        twilio.send_sms(
            business["on_call_transfer_number"],
            f"URGENT lead from {lead.full_name} ({lead.callback_number}): {lead.issue_summary}",
        )

    if lead:
        jobber.upsert_client(full_name=lead.full_name, phone=lead.callback_number, address=lead.service_address)

    crud.mark_call_log_processed(db, call_log)
