"""agent planning lease and tool step links

Revision ID: h8c9d0e1f2a3
Revises: g7b8c9d0e1f2
"""

import sqlalchemy as sa
from alembic import op

revision = "h8c9d0e1f2a3"
down_revision = "g7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_runs",
        sa.Column("planning_lease_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("tool_runs", sa.Column("turn_id", sa.UUID(), nullable=True))
    op.add_column("tool_runs", sa.Column("step_id", sa.String(length=32), nullable=True))
    op.add_column(
        "tool_runs",
        sa.Column("attempt", sa.Integer(), server_default="1", nullable=False),
    )
    op.create_foreign_key(
        "fk_tool_runs_turn", "tool_runs", "agent_runs", ["turn_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index(op.f("ix_tool_runs_turn_id"), "tool_runs", ["turn_id"], unique=False)
    op.create_index(
        "ix_tool_runs_turn_step", "tool_runs", ["turn_id", "step_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_tool_runs_turn_step", table_name="tool_runs")
    op.drop_index(op.f("ix_tool_runs_turn_id"), table_name="tool_runs")
    op.drop_constraint("fk_tool_runs_turn", "tool_runs", type_="foreignkey")
    op.drop_column("tool_runs", "attempt")
    op.drop_column("tool_runs", "step_id")
    op.drop_column("tool_runs", "turn_id")
    op.drop_column("agent_runs", "planning_lease_until")
