"""
/approvals — Human-in-the-loop approval gate.
Agents request approvals. Humans approve or reject via this API.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Approval
from logging_config import get_logger

router = APIRouter()
log = get_logger("approvals")


class RequestApprovalBody(BaseModel):
    project_id: Optional[str] = None
    run_id: Optional[str] = None
    action_type: str           # e.g. 'production_deploy', 'proposal_send', 'dns_change'
    requested_by_agent: str
    requested_to: Optional[str] = None
    rationale: Optional[str] = None
    metadata: Optional[dict] = None


class ReviewApprovalBody(BaseModel):
    decision: str              # 'approved' | 'rejected'
    approved_by: str
    rejection_reason: Optional[str] = None


@router.post("/request")
async def request_approval(body: RequestApprovalBody, db: AsyncSession = Depends(get_db)):
    approval = Approval(
        project_id=uuid.UUID(body.project_id) if body.project_id else None,
        run_id=uuid.UUID(body.run_id) if body.run_id else None,
        action_type=body.action_type,
        requested_by_agent=body.requested_by_agent,
        requested_to=body.requested_to,
        rationale=body.rationale,
        metadata=body.metadata,
        status="pending",
    )
    db.add(approval)
    await db.commit()
    await db.refresh(approval)

    log.info("approval_requested",
             approval_id=str(approval.id),
             action=body.action_type,
             agent=body.requested_by_agent)

    return {
        "id": str(approval.id),
        "action_type": approval.action_type,
        "status": approval.status,
        "requested_by_agent": approval.requested_by_agent,
    }


@router.post("/{approval_id}/review")
async def review_approval(
    approval_id: str,
    body: ReviewApprovalBody,
    db: AsyncSession = Depends(get_db)
):
    if body.decision not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="Decision must be 'approved' or 'rejected'")

    result = await db.execute(
        select(Approval).where(Approval.id == uuid.UUID(approval_id))
    )
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    if approval.status != "pending":
        raise HTTPException(status_code=409, detail=f"Approval already {approval.status}")

    approval.status = body.decision
    approval.approved_by = body.approved_by
    approval.approved_at = datetime.now(timezone.utc) if body.decision == "approved" else None
    approval.rejection_reason = body.rejection_reason

    await db.commit()
    await db.refresh(approval)

    log.info("approval_reviewed",
             approval_id=approval_id,
             decision=body.decision,
             by=body.approved_by)

    return {
        "id": str(approval.id),
        "action_type": approval.action_type,
        "status": approval.status,
        "approved_by": approval.approved_by,
        "approved_at": approval.approved_at,
    }


@router.get("/pending")
async def list_pending_approvals(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Approval).where(Approval.status == "pending").order_by(Approval.created_at.desc())
    )
    items = result.scalars().all()
    return [
        {
            "id": str(a.id),
            "action_type": a.action_type,
            "requested_by_agent": a.requested_by_agent,
            "rationale": a.rationale,
            "created_at": a.created_at,
        }
        for a in items
    ]
