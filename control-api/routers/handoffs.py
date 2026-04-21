"""
/handoffs — Record agent-to-agent handoffs with full payload and validation status.
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Handoff, AgentRun
from logging_config import get_logger

router = APIRouter()
log = get_logger("handoffs")


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


@router.post("/create", response_model=HandoffResponse)
async def create_handoff(body: CreateHandoffRequest, db: AsyncSession = Depends(get_db)):
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
