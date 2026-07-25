-- ---------------------------------------------------------------------------
-- AI Business Operator — initial schema
-- Source of truth for the Phase 2 database. From Phase 3 onward, schema changes
-- go through Alembic revisions rather than edits to this file.
-- ---------------------------------------------------------------------------

CREATE EXTENSION IF NOT EXISTS vector;

-- --- Identity --------------------------------------------------------------

CREATE TABLE IF NOT EXISTS users (
    user_id       SERIAL PRIMARY KEY,
    email         TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS projects (
    project_id SERIAL PRIMARY KEY,
    user_id    INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    goal       TEXT NOT NULL,                  -- e.g. 'Fitness ebook business'
    niche      TEXT,
    status     TEXT NOT NULL DEFAULT 'active', -- active | paused | blocked | completed
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_projects_user ON projects(user_id, status);

-- --- Agents and work -------------------------------------------------------

CREATE TABLE IF NOT EXISTS agents (
    agent_name    TEXT PRIMARY KEY,            -- e.g. 'research_agent'
    description   TEXT NOT NULL,
    allowed_tools TEXT[] NOT NULL DEFAULT '{}',
    is_enabled    BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tasks (
    task_id     SERIAL PRIMARY KEY,
    project_id  INT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    task_type   TEXT NOT NULL,                 -- e.g. 'create_product'
    assigned_to TEXT NOT NULL REFERENCES agents(agent_name),
    status      TEXT NOT NULL DEFAULT 'pending',
    input       JSONB NOT NULL DEFAULT '{}'::jsonb,
    output      JSONB,
    depends_on  INT[] NOT NULL DEFAULT '{}',
    attempts    INT NOT NULL DEFAULT 0,
    error       TEXT,
    claimed_by  TEXT,                          -- worker instance id
    claimed_at  TIMESTAMPTZ,
    approved_by INT REFERENCES users(user_id),
    approved_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ,
    CONSTRAINT tasks_status_valid CHECK (status IN (
        'pending', 'claimed', 'working', 'done',
        'error', 'awaiting_approval', 'blocked', 'cancelled'
    ))
);

-- Hot path: the worker claim query filters on exactly these two columns.
CREATE INDEX IF NOT EXISTS idx_tasks_project_status ON tasks(project_id, status);
CREATE INDEX IF NOT EXISTS idx_tasks_claimable ON tasks(assigned_to, status)
    WHERE status = 'pending';

-- --- Product and funnel artefacts ------------------------------------------

CREATE TABLE IF NOT EXISTS products (
    product_id   SERIAL PRIMARY KEY,
    project_id   INT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    name         TEXT NOT NULL,
    product_type TEXT,                         -- ebook | course | template | checklist
    price_cents  INT,
    currency     TEXT NOT NULL DEFAULT 'USD',
    content      JSONB,                        -- outline plus drafted sections
    systemeio_id TEXT,                         -- id in systeme.io once created
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS funnels (
    funnel_id    SERIAL PRIMARY KEY,
    project_id   INT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    name         TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'draft', -- draft | building | published
    systemeio_id TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS funnel_steps (
    step_id           SERIAL PRIMARY KEY,
    funnel_id         INT NOT NULL REFERENCES funnels(funnel_id) ON DELETE CASCADE,
    step_type         TEXT NOT NULL,            -- optin | sales | checkout | upsell | thankyou
    name              TEXT,
    page_content      JSONB,                    -- structured page data
    step_order        INT NOT NULL DEFAULT 0,   -- 'order' is reserved in SQL
    systemeio_step_id TEXT,
    systemeio_page_id TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (funnel_id, step_order)
);

CREATE TABLE IF NOT EXISTS emails (
    email_id      SERIAL PRIMARY KEY,
    project_id    INT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    sequence_name TEXT NOT NULL,
    subject       TEXT NOT NULL,
    body          TEXT NOT NULL,
    send_delay    INT NOT NULL DEFAULT 0,       -- hours after the previous email
    position      INT NOT NULL DEFAULT 0,
    systemeio_id  TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_emails_sequence ON emails(project_id, sequence_name, position);

-- --- Memory ----------------------------------------------------------------

CREATE TABLE IF NOT EXISTS memory_records (
    id              SERIAL PRIMARY KEY,
    project_id      INT REFERENCES projects(project_id) ON DELETE CASCADE,
    agent_name      TEXT REFERENCES agents(agent_name),
    category        TEXT NOT NULL,              -- customer_pain | headline | funnel_pattern | ...
    content         TEXT NOT NULL,
    embedding       VECTOR(1536),
    embedding_model TEXT,                       -- so mixed-model reads are detectable
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_important    BOOLEAN NOT NULL DEFAULT FALSE,
    expires_at      TIMESTAMPTZ,                -- NULL = no expiry (important records)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_memory_category ON memory_records(category, project_id);

-- Cosine similarity index. Tune `lists` to ~sqrt(row_count) once populated;
-- IVFFlat needs data present before the index is worth building, so this is
-- created here for convenience and should be REINDEXed after the first bulk load.
CREATE INDEX IF NOT EXISTS idx_memory_embedding ON memory_records
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- --- Analytics -------------------------------------------------------------

CREATE TABLE IF NOT EXISTS analytics_snapshots (
    snapshot_id SERIAL PRIMARY KEY,
    project_id  INT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    funnel_id   INT REFERENCES funnels(funnel_id) ON DELETE CASCADE,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metrics     JSONB NOT NULL                 -- visitors, optins, sales, revenue_cents
);

CREATE INDEX IF NOT EXISTS idx_analytics_project ON analytics_snapshots(project_id, captured_at DESC);

-- --- Seed the agent roster (mirrors AGENTS.md) -----------------------------

INSERT INTO agents (agent_name, description, allowed_tools) VALUES
    ('ceo_agent',          'Orchestrator: plans and assigns work',        ARRAY['task_queue','db_read','db_write','llm']),
    ('research_agent',     'Analyses market and competitors',             ARRAY['web_search','llm','memory_read','memory_write']),
    ('product_agent',      'Designs and drafts the digital product',      ARRAY['llm','memory_read','memory_write','file_write']),
    ('branding_agent',     'Generates brand identity',                    ARRAY['llm','image_gen','memory_read','memory_write']),
    ('copy_agent',         'Writes marketing copy',                       ARRAY['llm','memory_read','memory_write']),
    ('funnel_agent',       'Designs the funnel structure',                ARRAY['llm','db_read','memory_read','memory_write']),
    ('email_agent',        'Writes email sequences',                      ARRAY['llm','memory_read','memory_write']),
    ('automation_agent',   'Defines tags, triggers and delays',           ARRAY['systemeio_mcp','db_read','llm']),
    ('browser_agent',      'Drives the systeme.io UI via Playwright',     ARRAY['playwright','systemeio_api']),
    ('analytics_agent',    'Monitors results and metrics',                ARRAY['systemeio_api','db_read','metrics','llm']),
    ('optimization_agent', 'Proposes A/B tests and funnel tweaks',        ARRAY['llm','db_read','memory_read','memory_write'])
ON CONFLICT (agent_name) DO UPDATE
    SET description = EXCLUDED.description,
        allowed_tools = EXCLUDED.allowed_tools;
