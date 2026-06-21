from fastapi import FastAPI

from app.functions.book_visit import router as book_visit_router
from app.functions.cancel_visit import router as cancel_visit_router
from app.functions.capture_lead import router as capture_lead_router
from app.functions.check_availability import router as check_availability_router
from app.functions.flag_emergency import router as flag_emergency_router
from app.functions.reschedule_visit import router as reschedule_visit_router
from app.functions.transfer_to_human import router as transfer_to_human_router

app = FastAPI(title="Aireceptionist Backend")

app.include_router(check_availability_router)
app.include_router(book_visit_router)
app.include_router(reschedule_visit_router)
app.include_router(cancel_visit_router)
app.include_router(capture_lead_router)
app.include_router(flag_emergency_router)
app.include_router(transfer_to_human_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
