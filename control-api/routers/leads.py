"""
/leads — Lead ingestion and retrieval.
New leads trigger the intake workflow via Celery.
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Lead
from logging_config import get_logger

router = APIRouter()
log = get_logger("leads")


class CreateLeadBody(BaseModel):
    source: str                     # 'form', 'email', 'call', 'manual'
    company_name: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    service_interest: Optional[str] = None
    raw_payload: Optional[dict] = None
    notes: Optional[str] = None


def _trigger_intake_workflow(lead_id: str):
    """Fire-and-forget: enqueue the intake workflow in Celery."""
    try:
        from celery import Celery
        import os
        redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
        app = Celery(broker=redis_url)
        app.send_task(
            "worker.tasks.run_intake_workflow",
            args=[lead_id],
            queue="default",
        )
        log.info("intake_workflow_queued", lead_id=lead_id)
    except Exception as e:
        log.error("intake_workflow_queue_failed", lead_id=lead_id, error=str(e))


@router.post("/create")
async def create_lead(
    body: CreateLeadBody,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    lead = Lead(
        source=body.source,
        company_name=body.company_name,
        contact_name=body.contact_name,
        contact_email=body.contact_email,
        contact_phone=body.contact_phone,
        service_interest=body.service_interest,
        raw_payload=body.raw_payload,
        notes=body.notes,
        status="new",
    )
    db.add(lead)
    await db.commit()
    await db.refresh(lead)

    lead_id = str(lead.id)
    log.info("lead_created", lead_id=lead_id, source=body.source)

    # Trigger intake workflow async (won't block the API response)
    background_tasks.add_task(_trigger_intake_workflow, lead_id)

    return {
        "id": lead_id,
        "status": lead.status,
        "source": lead.source,
        "company_name": lead.company_name,
    }


@router.get("/{lead_id}")
async def get_lead(lead_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Lead).where(Lead.id == uuid.UUID(lead_id))
    )
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return {
        "id": str(lead.id),
        "source": lead.source,
        "company_name": lead.company_name,
        "contact_name": lead.contact_name,
        "contact_email": lead.contact_email,
        "service_interest": lead.service_interest,
        "status": lead.status,
        "qualification_score": float(lead.qualification_score) if lead.qualification_score else None,
        "created_at": lead.created_at,
    }


@router.get("/")
async def list_leads(status: Optional[str] = None, limit: int = 20, db: AsyncSession = Depends(get_db)):
    query = select(Lead).order_by(Lead.created_at.desc()).limit(limit)
    if status:
        query = query.where(Lead.status == status)
    result = await db.execute(query)
    leads = result.scalars().all()
    return [
        {
            "id": str(l.id),
            "source": l.source,
            "company_name": l.company_name,
            "status": l.status,
            "created_at": l.created_at,
        }
        for l in leads
    ]
