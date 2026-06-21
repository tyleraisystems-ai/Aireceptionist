from fastapi import FastAPI

from app.functions.check_availability import router as check_availability_router

app = FastAPI(title="Aireceptionist Backend")

app.include_router(check_availability_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
