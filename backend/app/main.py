from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from datetime import datetime, timezone

from backend.app.api import ingest, screen, audit
from backend.app.db.storage import init_db
from backend.app.logging_config import configure_logging
from backend.app.api import ingest, screen, audit, hitl, aims   # <- this one supersedes the first

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="lyzr-clinical-screen",
    description="Governed Clinical Trial Patient Screening & Regulatory Audit Agent",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(ingest.router)
app.include_router(screen.router)
app.include_router(audit.router)
app.include_router(hitl.router)
app.include_router(aims.router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "lyzr-clinical-screen-backend",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/")
async def root():
    return {"message": "lyzr-clinical-screen API is running. See /docs for endpoints."}

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield
