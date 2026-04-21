"""
/projects — Project CRUD. Projects group all runs, tasks, and deliverables.
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Project
from logging_config import get_logger

router = APIRouter()
log = get_logger("projects")


class CreateProjectBody(BaseModel):
    client_id: str
    type: str                       # 'website', 'automation', 'infra', 'maintenance'
    owner: Optional[str] = None
    notes: Optional[str] = None
    metadata: Optional[dict] = None


@router.post("/create")
async def create_project(body: CreateProjectBody, db: AsyncSession = Depends(get_db)):
    project = Project(
        client_id=uuid.UUID(body.client_id),
        type=body.type,
        owner=body.owner,
        notes=body.notes,
        metadata=body.metadata,
        status="planning",
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    log.info("project_created", project_id=str(project.id), type=body.type)
    return {"id": str(project.id), "type": project.type, "status": project.status}


@router.get("/{project_id}")
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Project).where(Project.id == uuid.UUID(project_id))
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return {
        "id": str(project.id),
        "client_id": str(project.client_id),
        "type": project.type,
        "status": project.status,
        "owner": project.owner,
        "notes": project.notes,
        "created_at": project.created_at,
    }


@router.get("/")
async def list_projects(limit: int = 20, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Project).order_by(Project.created_at.desc()).limit(limit)
    )
    projects = result.scalars().all()
    return [
        {"id": str(p.id), "type": p.type, "status": p.status, "owner": p.owner}
        for p in projects
    ]
