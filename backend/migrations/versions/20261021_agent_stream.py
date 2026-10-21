"""agent streaming turns and events

Revision ID: g7b8c9d0e1f2
Revises: f6a7b8c9d0e1
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "g7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_runs", sa.Column("idempotency_key", sa.String(length=80), nullable=True))
    op.add_column(
        "agent_runs",
        sa.Column(
            "phase",
            sa.Enum(
                "planning",
                "awaiting_confirmation",
                "executing",
                "completed",
                "failed",
                "canceled",
                "needs_attention",
                name="agentphase",
                native_enum=False,
                create_constraint=False,
                length=32,
            ),
            server_default="planning",
            nullable=False,
        ),
    )
    op.add_column(
        "agent_runs",
        sa.Column("planning_attempt", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column(
        "agent_runs",
        sa.Column(
            "plan_draft",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "agent_runs",
        sa.Column("public_summary", sa.Text(), server_default="", nullable=False),
    )
    op.add_column(
        "agent_runs",
        sa.Column("plan_version", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "agent_runs",
        sa.Column("checkpoint_thread_id", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "agent_runs",
        sa.Column("last_event_seq", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_unique_constraint(
        "uq_turn_user_request", "agent_runs", ["user_id", "idempotency_key"]
    )
    op.create_index(op.f("ix_agent_runs_phase"), "agent_runs", ["phase"], unique=False)

    # 老轮次按现有状态回填真实阶段，避免刷新后全部显示「规划中」
    op.execute(
        """
        UPDATE agent_runs SET phase = CASE status
            WHEN 'queued' THEN 'awaiting_confirmation'
            WHEN 'running' THEN 'executing'
            WHEN 'succeeded' THEN 'completed'
            WHEN 'failed' THEN 'failed'
            WHEN 'canceled' THEN 'canceled'
            ELSE 'completed'
        END
        """
    )

    op.create_table(
        "agent_events",
        sa.Column("turn_id", sa.UUID(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=48), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["turn_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("turn_id", "seq", name="uq_agent_event_seq"),
    )
    op.create_index(op.f("ix_agent_events_turn_id"), "agent_events", ["turn_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_agent_events_turn_id"), table_name="agent_events")
    op.drop_table("agent_events")
    op.drop_index(op.f("ix_agent_runs_phase"), table_name="agent_runs")
    op.drop_constraint("uq_turn_user_request", "agent_runs", type_="unique")
    op.drop_column("agent_runs", "last_event_seq")
    op.drop_column("agent_runs", "checkpoint_thread_id")
    op.drop_column("agent_runs", "plan_version")
    op.drop_column("agent_runs", "public_summary")
    op.drop_column("agent_runs", "plan_draft")
    op.drop_column("agent_runs", "planning_attempt")
    op.drop_column("agent_runs", "phase")
    op.drop_column("agent_runs", "idempotency_key")
