"""
/runs — Agent run lifecycle: create, complete, retrieve.
Every agent execution gets a run_id. Results are stored here.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import AgentRun
from logging_config import get_logger

router = APIRouter()
log = get_logger("runs")


# ─── Schemas ─────────────────────────────────────────────────────────────────

class CreateRunRequest(BaseModel):
    project_id: Optional[str] = None
    task_id: Optional[str] = None
    agent_name: str
    model_alias: Optional[str] = "standard_worker"
    input_payload: Optional[dict] = None


class CompleteRunRequest(BaseModel):
    result_status: str  # success | failure | escalated | timeout
    output_payload: Optional[dict] = None
    model_used: Optional[str] = None
    token_usage: Optional[dict] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class RunResponse(BaseModel):
    id: str
    run_id: str
    agent_name: str
    model_alias: Optional[str]
    result_status: Optional[str]
    started_at: datetime
    ended_at: Optional[datetime]

    class Config:
        from_attributes = True


# ─── Routes ──────────────────────────────────────────────────────────────────

@router.post("/create", response_model=RunResponse)
async def create_run(body: CreateRunRequest, db: AsyncSession = Depends(get_db)):
    run = AgentRun(
        run_id=uuid.uuid4(),
        project_id=body.project_id,
        task_id=body.task_id,
        agent_name=body.agent_name,
        model_alias=body.model_alias,
        input_payload=body.input_payload,
        started_at=datetime.now(timezone.utc),
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    log.info("run_created", run_id=str(run.run_id), agent=run.agent_name)
    return _to_response(run)


@router.post("/{run_id}/complete", response_model=RunResponse)
async def complete_run(run_id: str, body: CompleteRunRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AgentRun).where(AgentRun.run_id == uuid.UUID(run_id))
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    run.result_status = body.result_status
    run.output_payload = body.output_payload
    run.model_used = body.model_used
    run.token_usage = body.token_usage
    run.error_code = body.error_code
    run.error_message = body.error_message
    run.ended_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(run)
    log.info("run_completed", run_id=run_id, status=body.result_status)
    return _to_response(run)


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(run_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AgentRun).where(AgentRun.run_id == uuid.UUID(run_id))
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return _to_response(run)


@router.get("/")
async def list_runs(limit: int = 20, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AgentRun).order_by(AgentRun.started_at.desc()).limit(limit)
    )
    runs = result.scalars().all()
    return [_to_response(r) for r in runs]


def _to_response(run: AgentRun) -> dict:
    return {
        "id": str(run.id),
        "run_id": str(run.run_id),
        "agent_name": run.agent_name,
        "model_alias": run.model_alias,
        "result_status": run.result_status,
        "started_at": run.started_at,
        "ended_at": run.ended_at,
    }
