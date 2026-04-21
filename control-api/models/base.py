"""
SQLAlchemy ORM models — mirror of postgres/init.sql schema.
All IDs are UUIDs. All JSON payloads use JSONB.
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, Integer, SmallInteger, Boolean,
    Numeric, DateTime, ForeignKey, ARRAY, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from database import Base


def _uuid():
    return str(uuid.uuid4())


class Lead(Base):
    __tablename__ = "leads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(String(100), nullable=False)
    company_name = Column(String(255))
    contact_name = Column(String(255))
    contact_email = Column(String(255))
    contact_phone = Column(String(50))
    service_interest = Column(String(255))
    raw_payload = Column(JSONB)
    status = Column(String(50), nullable=False, default="new")
    qualification_score = Column(Numeric(4, 2))
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Client(Base):
    __tablename__ = "clients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id"))
    legal_name = Column(String(255), nullable=False)
    brand_name = Column(String(255))
    domains = Column(ARRAY(Text))
    primary_contacts = Column(JSONB)
    billing_meta = Column(JSONB)
    notes = Column(Text)
    status = Column(String(50), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False)
    type = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False, default="planning")
    scope_version = Column(Integer, nullable=False, default=1)
    owner = Column(String(255))
    start_date = Column(DateTime(timezone=True))
    target_date = Column(DateTime(timezone=True))
    notes = Column(Text)
    meta = Column("metadata", JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Task(Base):
    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"))
    agent_name = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False, default="pending")
    priority = Column(SmallInteger, nullable=False, default=2)
    input_ref = Column(Text)
    output_ref = Column(Text)
    depends_on = Column(ARRAY(UUID(as_uuid=True)))
    meta = Column("metadata", JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"))
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"))
    agent_name = Column(String(100), nullable=False)
    prompt_version_id = Column(UUID(as_uuid=True))
    model_used = Column(String(100))
    model_alias = Column(String(100))
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    ended_at = Column(DateTime(timezone=True))
    result_status = Column(String(50))
    input_payload = Column(JSONB)
    output_payload = Column(JSONB)
    token_usage = Column(JSONB)
    error_code = Column(String(100))
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Handoff(Base):
    __tablename__ = "handoffs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    from_run_id = Column(UUID(as_uuid=True), ForeignKey("agent_runs.id"), nullable=False)
    to_agent = Column(String(100), nullable=False)
    payload_json = Column(JSONB, nullable=False)
    schema_version = Column(String(20), nullable=False, default="1.0")
    validation_status = Column(String(50), nullable=False, default="pending")
    validation_errors = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Approval(Base):
    __tablename__ = "approvals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"))
    run_id = Column(UUID(as_uuid=True), ForeignKey("agent_runs.id"))
    action_type = Column(String(100), nullable=False)
    requested_by_agent = Column(String(100), nullable=False)
    requested_to = Column(String(255))
    status = Column(String(50), nullable=False, default="pending")
    rationale = Column(Text)
    approved_at = Column(DateTime(timezone=True))
    approved_by = Column(String(255))
    rejection_reason = Column(Text)
    meta = Column("metadata", JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(UUID(as_uuid=True), nullable=False)
    actor_type = Column(String(50), nullable=False)
    actor_id = Column(String(255))
    event_type = Column(String(100), nullable=False)
    payload_json = Column(JSONB)
    request_id = Column(UUID(as_uuid=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
