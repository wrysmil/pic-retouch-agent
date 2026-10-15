"""collapse runtime config to text + image slots

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # model_definitions：能力矩阵 -> 单一类型（文本/生图）+ 可选编辑模型 ID
    op.drop_column("model_definitions", "capabilities")
    op.add_column(
        "model_definitions",
        sa.Column("model_type", sa.String(length=16), nullable=False, server_default="text"),
    )
    op.alter_column("model_definitions", "model_type", server_default=None)
    op.add_column(
        "model_definitions",
        sa.Column("edit_vendor_model_id", sa.String(length=128), nullable=True),
    )

    # runtime_config_versions：6 个槽位（规划/生成/编辑）-> 4 个（文本/生图）
    for col in (
        "planner_model_id",
        "planner_connection_version_id",
        "text_to_image_model_id",
        "text_to_image_connection_version_id",
        "image_edit_model_id",
        "image_edit_connection_version_id",
    ):
        op.drop_constraint(
            f"runtime_config_versions_{col}_fkey", "runtime_config_versions", type_="foreignkey"
        )
        op.drop_column("runtime_config_versions", col)

    op.add_column("runtime_config_versions", sa.Column("text_model_id", sa.UUID(), nullable=True))
    op.add_column(
        "runtime_config_versions",
        sa.Column("text_connection_version_id", sa.UUID(), nullable=True),
    )
    op.add_column("runtime_config_versions", sa.Column("image_model_id", sa.UUID(), nullable=True))
    op.add_column(
        "runtime_config_versions",
        sa.Column("image_connection_version_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_runtime_config_versions_text_model_id",
        "runtime_config_versions",
        "model_definitions",
        ["text_model_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_runtime_config_versions_text_connection_version_id",
        "runtime_config_versions",
        "model_connection_versions",
        ["text_connection_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_runtime_config_versions_image_model_id",
        "runtime_config_versions",
        "model_definitions",
        ["image_model_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_runtime_config_versions_image_connection_version_id",
        "runtime_config_versions",
        "model_connection_versions",
        ["image_connection_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.alter_column("runtime_config_versions", "text_model_id", nullable=False)
    op.alter_column("runtime_config_versions", "text_connection_version_id", nullable=False)
    op.alter_column("runtime_config_versions", "image_model_id", nullable=False)
    op.alter_column("runtime_config_versions", "image_connection_version_id", nullable=False)


def downgrade() -> None:
    for name in (
        "fk_runtime_config_versions_image_connection_version_id",
        "fk_runtime_config_versions_image_model_id",
        "fk_runtime_config_versions_text_connection_version_id",
        "fk_runtime_config_versions_text_model_id",
    ):
        op.drop_constraint(name, "runtime_config_versions", type_="foreignkey")
    for col in (
        "image_connection_version_id",
        "image_model_id",
        "text_connection_version_id",
        "text_model_id",
    ):
        op.drop_column("runtime_config_versions", col)

    op.add_column(
        "runtime_config_versions", sa.Column("planner_model_id", sa.UUID(), nullable=True)
    )
    op.add_column(
        "runtime_config_versions",
        sa.Column("planner_connection_version_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "runtime_config_versions", sa.Column("text_to_image_model_id", sa.UUID(), nullable=True)
    )
    op.add_column(
        "runtime_config_versions",
        sa.Column("text_to_image_connection_version_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "runtime_config_versions", sa.Column("image_edit_model_id", sa.UUID(), nullable=True)
    )
    op.add_column(
        "runtime_config_versions",
        sa.Column("image_edit_connection_version_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "runtime_config_versions_planner_model_id_fkey",
        "runtime_config_versions",
        "model_definitions",
        ["planner_model_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "runtime_config_versions_planner_connection_version_id_fkey",
        "runtime_config_versions",
        "model_connection_versions",
        ["planner_connection_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "runtime_config_versions_text_to_image_model_id_fkey",
        "runtime_config_versions",
        "model_definitions",
        ["text_to_image_model_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "runtime_config_versions_text_to_image_connection_version_id_fkey",
        "runtime_config_versions",
        "model_connection_versions",
        ["text_to_image_connection_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "runtime_config_versions_image_edit_model_id_fkey",
        "runtime_config_versions",
        "model_definitions",
        ["image_edit_model_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "runtime_config_versions_image_edit_connection_version_id_fkey",
        "runtime_config_versions",
        "model_connection_versions",
        ["image_edit_connection_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.drop_column("model_definitions", "edit_vendor_model_id")
    op.drop_column("model_definitions", "model_type")
    op.add_column(
        "model_definitions",
        sa.Column(
            "capabilities",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
