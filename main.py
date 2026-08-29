from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.api.routes import router
from app.core.database import engine
from app.models import Base  # imports Transaction + AuditLog so both register


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(title="Revenue Recovery Agent API", lifespan=lifespan)
app.include_router(router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "healthy"}