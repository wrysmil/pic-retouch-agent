"""add runtime_config_version to runs

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
"""

import sqlalchemy as sa
from alembic import op

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 老库已有 agent_runs / tool_runs 时给它们补一列运行时配置版本。
    # 这一列可空：未发布前的数据不带版本，方便后续重新解析补齐
    op.add_column(
        "agent_runs",
        sa.Column("runtime_config_version_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "tool_runs",
        sa.Column("runtime_config_version_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_agent_runs_runtime_config_version",
        "agent_runs",
        "runtime_config_versions",
        ["runtime_config_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_tool_runs_runtime_config_version",
        "tool_runs",
        "runtime_config_versions",
        ["runtime_config_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_agent_runs_runtime_config_version_id",
        "agent_runs",
        ["runtime_config_version_id"],
        unique=False,
    )
    op.create_index(
        "ix_tool_runs_runtime_config_version_id",
        "tool_runs",
        ["runtime_config_version_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tool_runs_runtime_config_version_id", table_name="tool_runs"
    )
    op.drop_index(
        "ix_agent_runs_runtime_config_version_id", table_name="agent_runs"
    )
    op.drop_constraint(
        "fk_tool_runs_runtime_config_version", "tool_runs", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_agent_runs_runtime_config_version", "agent_runs", type_="foreignkey"
    )
    op.drop_column("tool_runs", "runtime_config_version_id")
    op.drop_column("agent_runs", "runtime_config_version_id")