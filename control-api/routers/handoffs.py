"""
/handoffs — Record agent-to-agent handoffs with full payload and validation status.
Creating a handoff also dispatches the next agent run via Celery.
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Handoff, AgentRun
from logging_config import get_logger

router = APIRouter()
log = get_logger("handoffs")


def _dispatch_next_agent(to_agent: str, run_id: str, payload: dict):
    """Fire-and-forget: enqueue the next agent in the chain via Celery."""
    try:
        from celery import Celery
        import os
        redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
        app = Celery(broker=redis_url)
        app.send_task(
            "worker.tasks.run_agent",
            args=[run_id, to_agent, payload],
            queue="agent_runs",
        )
        log.info("next_agent_dispatched", to_agent=to_agent, run_id=run_id)
    except Exception as e:
        log.error("dispatch_failed", to_agent=to_agent, error=str(e))


class CreateHandoffRequest(BaseModel):
    from_run_id: str        # DB UUID of the source AgentRun row
    to_agent: str
    payload_json: dict
    schema_version: str = "1.0"


class HandoffResponse(BaseModel):
    id: str
    from_run_id: str
    to_agent: str
    schema_version: str
    validation_status: str


@router.get("/")
async def list_handoffs(limit: int = 20, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Handoff).order_by(Handoff.created_at.desc()).limit(limit)
    )
    handoffs = result.scalars().all()
    return [
        {
            "id": str(h.id),
            "from_run_id": str(h.from_run_id),
            "to_agent": h.to_agent,
            "schema_version": h.schema_version,
            "validation_status": h.validation_status,
            "created_at": h.created_at,
        }
        for h in handoffs
    ]


@router.post("/create", response_model=HandoffResponse)
async def create_handoff(
    body: CreateHandoffRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    # Verify source run exists
    run_result = await db.execute(
        select(AgentRun).where(AgentRun.id == uuid.UUID(body.from_run_id))
    )
    source_run = run_result.scalar_one_or_none()
    if not source_run:
        raise HTTPException(status_code=404, detail=f"Source run {body.from_run_id} not found")

    handoff = Handoff(
        from_run_id=uuid.UUID(body.from_run_id),
        to_agent=body.to_agent,
        payload_json=body.payload_json,
        schema_version=body.schema_version,
        validation_status="pending",
    )
    db.add(handoff)
    await db.commit()
    await db.refresh(handoff)

    log.info("handoff_created",
             handoff_id=str(handoff.id),
             from_run=body.from_run_id,
             to_agent=body.to_agent)

    # Create a new run for the next agent and dispatch it
    next_run = AgentRun(
        run_id=uuid.uuid4(),
        agent_name=body.to_agent,
        model_alias="standard_worker",
        input_payload=body.payload_json,
    )
    db.add(next_run)
    await db.commit()
    await db.refresh(next_run)

    background_tasks.add_task(
        _dispatch_next_agent,
        body.to_agent,
        str(next_run.run_id),
        body.payload_json,
    )

    return {
        "id": str(handoff.id),
        "from_run_id": str(handoff.from_run_id),
        "to_agent": handoff.to_agent,
        "schema_version": handoff.schema_version,
        "validation_status": handoff.validation_status,
    }


@router.get("/{handoff_id}")
async def get_handoff(handoff_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Handoff).where(Handoff.id == uuid.UUID(handoff_id))
    )
    handoff = result.scalar_one_or_none()
    if not handoff:
        raise HTTPException(status_code=404, detail="Handoff not found")
    return {
        "id": str(handoff.id),
        "from_run_id": str(handoff.from_run_id),
        "to_agent": handoff.to_agent,
        "payload_json": handoff.payload_json,
        "schema_version": handoff.schema_version,
        "validation_status": handoff.validation_status,
    }
