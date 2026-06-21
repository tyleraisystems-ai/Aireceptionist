from pydantic import BaseModel


class CallAnalysis(BaseModel):
    call_summary: str | None = None
    user_sentiment: str | None = None
    call_successful: bool | None = None
    in_voicemail: bool | None = None
    custom_analysis_data: dict | None = None


class PostCallCall(BaseModel):
    call_id: str
    from_number: str | None = None
    to_number: str | None = None
    call_status: str | None = None
    transcript: str | None = None
    start_timestamp: int | None = None
    end_timestamp: int | None = None
    disconnection_reason: str | None = None
    call_analysis: CallAnalysis | None = None


class PostCallWebhook(BaseModel):
    event: str  # call_started | call_ended | call_analyzed
    call: PostCallCall
