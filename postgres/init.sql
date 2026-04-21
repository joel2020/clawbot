-- Clawbot — Postgres Schema
-- Run automatically on first container start via docker-entrypoint-initdb.d
-- All IDs are UUIDs. All JSON payloads use JSONB.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ─── Leads ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS leads (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source              VARCHAR(100) NOT NULL,           -- 'form', 'email', 'call', 'manual'
    company_name        VARCHAR(255),
    contact_name        VARCHAR(255),
    contact_email       VARCHAR(255),
    contact_phone       VARCHAR(50),
    service_interest    VARCHAR(255),
    raw_payload         JSONB,
    status              VARCHAR(50) NOT NULL DEFAULT 'new',  -- new, qualified, disqualified, converted
    qualification_score NUMERIC(4,2),
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Clients ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS clients (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id             UUID REFERENCES leads(id),
    legal_name          VARCHAR(255) NOT NULL,
    brand_name          VARCHAR(255),
    domains             TEXT[],
    primary_contacts    JSONB,          -- [{name, email, role}]
    billing_meta        JSONB,
    notes               TEXT,
    status              VARCHAR(50) NOT NULL DEFAULT 'active',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Projects ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS projects (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id           UUID NOT NULL REFERENCES clients(id),
    type                VARCHAR(100) NOT NULL,   -- 'website', 'automation', 'infra', 'maintenance'
    status              VARCHAR(50) NOT NULL DEFAULT 'planning',
    scope_version       INTEGER NOT NULL DEFAULT 1,
    owner               VARCHAR(255),
    start_date          DATE,
    target_date         DATE,
    notes               TEXT,
    metadata            JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Tasks ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tasks (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID REFERENCES projects(id),
    agent_name          VARCHAR(100) NOT NULL,
    status              VARCHAR(50) NOT NULL DEFAULT 'pending',
    priority            SMALLINT NOT NULL DEFAULT 2,    -- 1=high, 2=normal, 3=low
    input_ref           TEXT,           -- storage URI or inline JSON key
    output_ref          TEXT,
    depends_on          UUID[],         -- array of task IDs
    metadata            JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Agent Runs ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agent_runs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id              UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    project_id          UUID REFERENCES projects(id),
    task_id             UUID REFERENCES tasks(id),
    agent_name          VARCHAR(100) NOT NULL,
    prompt_version_id   UUID,
    model_used          VARCHAR(100),
    model_alias         VARCHAR(100),
    started_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at            TIMESTAMPTZ,
    result_status       VARCHAR(50),    -- success, failure, escalated, timeout
    input_payload       JSONB,
    output_payload      JSONB,
    token_usage         JSONB,          -- {prompt_tokens, completion_tokens, total_tokens, cost_usd}
    error_code          VARCHAR(100),
    error_message       TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Handoffs ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS handoffs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_run_id         UUID NOT NULL REFERENCES agent_runs(id),
    to_agent            VARCHAR(100) NOT NULL,
    payload_json        JSONB NOT NULL,
    schema_version      VARCHAR(20) NOT NULL DEFAULT '1.0',
    validation_status   VARCHAR(50) NOT NULL DEFAULT 'pending',  -- pending, valid, invalid
    validation_errors   JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Approvals ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS approvals (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID REFERENCES projects(id),
    run_id              UUID REFERENCES agent_runs(id),
    action_type         VARCHAR(100) NOT NULL,   -- 'production_deploy', 'proposal_send', 'dns_change', etc.
    requested_by_agent  VARCHAR(100) NOT NULL,
    requested_to        VARCHAR(255),            -- email or role
    status              VARCHAR(50) NOT NULL DEFAULT 'pending',  -- pending, approved, rejected
    rationale           TEXT,
    approved_at         TIMESTAMPTZ,
    approved_by         VARCHAR(255),
    rejection_reason    TEXT,
    metadata            JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Deliverables ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS deliverables (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID NOT NULL REFERENCES projects(id),
    run_id              UUID REFERENCES agent_runs(id),
    type                VARCHAR(100) NOT NULL,   -- 'proposal', 'strategy_brief', 'build_plan', 'sop', etc.
    name                VARCHAR(255),
    storage_uri         TEXT,
    version             INTEGER NOT NULL DEFAULT 1,
    approved            BOOLEAN NOT NULL DEFAULT FALSE,
    checksum            VARCHAR(64),
    metadata            JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Prompt Versions ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS prompt_versions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name          VARCHAR(100) NOT NULL,
    version             VARCHAR(20) NOT NULL,
    template_text       TEXT NOT NULL,
    schema_json         JSONB,
    active              BOOLEAN NOT NULL DEFAULT FALSE,
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (agent_name, version)
);

-- ─── SOPs ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sops (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID REFERENCES projects(id),
    title               VARCHAR(255) NOT NULL,
    version             INTEGER NOT NULL DEFAULT 1,
    storage_uri         TEXT,
    status              VARCHAR(50) NOT NULL DEFAULT 'draft',   -- draft, approved, published
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Errors ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS errors (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id              UUID REFERENCES agent_runs(id),
    severity            VARCHAR(20) NOT NULL DEFAULT 'error',   -- debug, info, warning, error, critical
    code                VARCHAR(100),
    message             TEXT NOT NULL,
    root_cause          TEXT,
    recovery_action     TEXT,
    resolved            BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Activity Log ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS activity_logs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type         VARCHAR(50) NOT NULL,   -- 'lead', 'project', 'run', 'approval', etc.
    entity_id           UUID NOT NULL,
    actor_type          VARCHAR(50) NOT NULL,   -- 'agent', 'human', 'system'
    actor_id            VARCHAR(255),
    event_type          VARCHAR(100) NOT NULL,
    payload_json        JSONB,
    request_id          UUID,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Indexes ─────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
CREATE INDEX IF NOT EXISTS idx_leads_created_at ON leads(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_projects_client_id ON projects(client_id);
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
CREATE INDEX IF NOT EXISTS idx_tasks_project_id ON tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_agent_runs_run_id ON agent_runs(run_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_project_id ON agent_runs(project_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_agent_name ON agent_runs(agent_name);
CREATE INDEX IF NOT EXISTS idx_agent_runs_started_at ON agent_runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_handoffs_from_run_id ON handoffs(from_run_id);
CREATE INDEX IF NOT EXISTS idx_approvals_status ON approvals(status);
CREATE INDEX IF NOT EXISTS idx_approvals_project_id ON approvals(project_id);
CREATE INDEX IF NOT EXISTS idx_activity_logs_entity ON activity_logs(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_activity_logs_created_at ON activity_logs(created_at DESC);

-- ─── Updated At Trigger ──────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER leads_updated_at BEFORE UPDATE ON leads FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER clients_updated_at BEFORE UPDATE ON clients FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER projects_updated_at BEFORE UPDATE ON projects FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER tasks_updated_at BEFORE UPDATE ON tasks FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER approvals_updated_at BEFORE UPDATE ON approvals FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER sops_updated_at BEFORE UPDATE ON sops FOR EACH ROW EXECUTE FUNCTION update_updated_at();
