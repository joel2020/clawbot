"""
Clawbot — Control API
FastAPI service: run tracking, handoffs, approvals, projects, leads.
Every request gets a correlation ID injected into structlog context.
"""
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import get_settings
from logging_config import configure_logging, get_logger
from routers import runs, handoffs, approvals, projects, leads

configure_logging()
log = get_logger("control-api")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("control_api_starting", environment=settings.environment)
    yield
    log.info("control_api_stopping")


app = FastAPI(
    title="Clawbot Control API",
    version="1.0.0",
    description="Orchestration spine for the Clawbot multi-agent OS",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production — restrict to your domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Correlation ID middleware ────────────────────────────────────────────────

@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# ─── Routers ─────────────────────────────────────────────────────────────────

app.include_router(runs.router, prefix="/runs", tags=["Agent Runs"])
app.include_router(handoffs.router, prefix="/handoffs", tags=["Handoffs"])
app.include_router(approvals.router, prefix="/approvals", tags=["Approvals"])
app.include_router(projects.router, prefix="/projects", tags=["Projects"])
app.include_router(leads.router, prefix="/leads", tags=["Leads"])


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
async def health():
    return {"status": "ok", "service": "clawbot-control-api"}


@app.get("/", tags=["System"])
async def root():
    return {"service": "Clawbot Control API", "docs": "/docs"}
