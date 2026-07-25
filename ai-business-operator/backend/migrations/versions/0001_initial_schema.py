"""Initial schema

Mirrors infra/sql/001_init.sql, which stays as the reference DDL and the
docker-compose init script. This revision is the authoritative path for applying
and evolving the schema from here on.

Revision ID: 0001
Revises:
Create Date: 2026-07-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TASK_STATUSES = (
    "pending",
    "claimed",
    "working",
    "done",
    "error",
    "awaiting_approval",
    "blocked",
    "cancelled",
)

AGENT_SEED = [
    (
        "ceo_agent",
        "Orchestrator: plans and assigns work",
        ["task_queue", "db_read", "db_write", "llm"],
    ),
    (
        "research_agent",
        "Analyses market and competitors",
        ["web_search", "llm", "memory_read", "memory_write"],
    ),
    (
        "product_agent",
        "Designs and drafts the digital product",
        ["llm", "memory_read", "memory_write", "file_write"],
    ),
    (
        "branding_agent",
        "Generates brand identity",
        ["llm", "image_gen", "memory_read", "memory_write"],
    ),
    ("copy_agent", "Writes marketing copy", ["llm", "memory_read", "memory_write"]),
    (
        "funnel_agent",
        "Designs the funnel structure",
        ["llm", "db_read", "memory_read", "memory_write"],
    ),
    ("email_agent", "Writes email sequences", ["llm", "memory_read", "memory_write"]),
    ("automation_agent", "Defines tags, triggers and delays", ["systemeio_mcp", "db_read", "llm"]),
    ("browser_agent", "Drives the systeme.io UI via Playwright", ["playwright", "systemeio_api"]),
    (
        "analytics_agent",
        "Monitors results and metrics",
        ["systemeio_api", "db_read", "metrics", "llm"],
    ),
    (
        "optimization_agent",
        "Proposes A/B tests and funnel tweaks",
        ["llm", "db_read", "memory_read", "memory_write"],
    ),
]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "users",
        sa.Column("user_id", sa.Integer, primary_key=True),
        sa.Column("email", sa.Text, nullable=False, unique=True),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "projects",
        sa.Column("project_id", sa.Integer, primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("goal", sa.Text, nullable=False),
        sa.Column("niche", sa.Text),
        sa.Column("status", sa.Text, nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_index("idx_projects_user", "projects", ["user_id", "status"])

    op.create_table(
        "agents",
        sa.Column("agent_name", sa.Text, primary_key=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column(
            "allowed_tools",
            postgresql.ARRAY(sa.Text),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "tasks",
        sa.Column("task_id", sa.Integer, primary_key=True),
        sa.Column(
            "project_id",
            sa.Integer,
            sa.ForeignKey("projects.project_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("task_type", sa.Text, nullable=False),
        sa.Column("assigned_to", sa.Text, sa.ForeignKey("agents.agent_name"), nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        sa.Column("input", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("output", postgresql.JSONB),
        sa.Column("depends_on", postgresql.ARRAY(sa.Integer), nullable=False, server_default="{}"),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error", sa.Text),
        sa.Column("claimed_by", sa.Text),
        sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.Column("approved_by", sa.Integer, sa.ForeignKey("users.user_id")),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN (" + ", ".join(f"'{s}'" for s in TASK_STATUSES) + ")",
            name="tasks_status_valid",
        ),
    )
    # The worker claim query filters on exactly these columns.
    op.create_index("idx_tasks_project_status", "tasks", ["project_id", "status"])
    op.create_index(
        "idx_tasks_claimable",
        "tasks",
        ["assigned_to", "status"],
        postgresql_where=sa.text("status = 'pending'"),
    )

    op.create_table(
        "products",
        sa.Column("product_id", sa.Integer, primary_key=True),
        sa.Column(
            "project_id",
            sa.Integer,
            sa.ForeignKey("projects.project_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("product_type", sa.Text),
        sa.Column("price_cents", sa.Integer),
        sa.Column("currency", sa.Text, nullable=False, server_default="USD"),
        sa.Column("content", postgresql.JSONB),
        sa.Column("systemeio_id", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "funnels",
        sa.Column("funnel_id", sa.Integer, primary_key=True),
        sa.Column(
            "project_id",
            sa.Integer,
            sa.ForeignKey("projects.project_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="draft"),
        sa.Column("systemeio_id", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "funnel_steps",
        sa.Column("step_id", sa.Integer, primary_key=True),
        sa.Column(
            "funnel_id",
            sa.Integer,
            sa.ForeignKey("funnels.funnel_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("step_type", sa.Text, nullable=False),
        sa.Column("name", sa.Text),
        sa.Column("page_content", postgresql.JSONB),
        sa.Column("step_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("systemeio_step_id", sa.Text),
        sa.Column("systemeio_page_id", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("funnel_id", "step_order"),
    )

    op.create_table(
        "emails",
        sa.Column("email_id", sa.Integer, primary_key=True),
        sa.Column(
            "project_id",
            sa.Integer,
            sa.ForeignKey("projects.project_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence_name", sa.Text, nullable=False),
        sa.Column("subject", sa.Text, nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("send_delay", sa.Integer, nullable=False, server_default="0"),
        sa.Column("position", sa.Integer, nullable=False, server_default="0"),
        sa.Column("systemeio_id", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_emails_sequence", "emails", ["project_id", "sequence_name", "position"])

    op.create_table(
        "memory_records",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "project_id", sa.Integer, sa.ForeignKey("projects.project_id", ondelete="CASCADE")
        ),
        sa.Column("agent_name", sa.Text, sa.ForeignKey("agents.agent_name")),
        sa.Column("category", sa.Text, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("embedding_model", sa.Text),
        sa.Column(
            "metadata", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("is_important", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    # Added as raw SQL: Alembic has no type for pgvector's `vector`.
    op.execute("ALTER TABLE memory_records ADD COLUMN embedding VECTOR(1536)")
    op.create_index("idx_memory_category", "memory_records", ["category", "project_id"])
    # IVFFlat clusters from existing rows, so this is near-useless until the table
    # has data. Rebuild it after the first bulk load — see vector_memory/index_setup.sql.
    op.execute(
        "CREATE INDEX idx_memory_embedding ON memory_records "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )

    op.create_table(
        "analytics_snapshots",
        sa.Column("snapshot_id", sa.Integer, primary_key=True),
        sa.Column(
            "project_id",
            sa.Integer,
            sa.ForeignKey("projects.project_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("funnel_id", sa.Integer, sa.ForeignKey("funnels.funnel_id", ondelete="CASCADE")),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("metrics", postgresql.JSONB, nullable=False),
    )
    op.create_index(
        "idx_analytics_project",
        "analytics_snapshots",
        ["project_id", sa.text("captured_at DESC")],
    )

    # Seed the agent roster. tasks.assigned_to is a foreign key onto this table, so
    # it must be populated before any task can be created.
    agents = sa.table(
        "agents",
        sa.column("agent_name", sa.Text),
        sa.column("description", sa.Text),
        sa.column("allowed_tools", postgresql.ARRAY(sa.Text)),
    )
    op.bulk_insert(
        agents,
        [
            {"agent_name": name, "description": desc, "allowed_tools": tools}
            for name, desc, tools in AGENT_SEED
        ],
    )


def downgrade() -> None:
    for table in (
        "analytics_snapshots",
        "memory_records",
        "emails",
        "funnel_steps",
        "funnels",
        "products",
        "tasks",
        "agents",
        "projects",
        "users",
    ):
        op.drop_table(table)
    # The vector extension is left in place: other databases in the cluster may use
    # it, and dropping an extension is not this migration's business.
