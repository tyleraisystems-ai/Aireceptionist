from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import Base, get_engine
from app.retell.functions import router as functions_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=get_engine())
    yield


app = FastAPI(title="AI Receptionist - Retell Custom Functions", lifespan=lifespan)
app.include_router(functions_router, prefix="/retell/functions", tags=["retell-functions"])


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
