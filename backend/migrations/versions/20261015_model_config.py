"""model config tables

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_connections",
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("vendor", sa.String(length=32), nullable=False),
        sa.Column(
            "adapter_type",
            sa.String(length=16),
            nullable=False,
        ),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("current_version_id", sa.UUID(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="active",
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )

    op.create_table(
        "model_connection_versions",
        sa.Column("connection_id", sa.UUID(), nullable=False),
        sa.Column("version_seq", sa.Integer(), nullable=False),
        sa.Column("base_url", sa.String(length=512), nullable=False),
        sa.Column("encrypted_api_key", sa.Text(), nullable=False),
        sa.Column(
            "extra",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["connection_id"], ["model_connections.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("connection_id", "version_seq", name="uq_conn_version"),
    )
    op.create_index(
        "ix_model_connection_versions_connection_id",
        "model_connection_versions",
        ["connection_id"],
        unique=False,
    )

    op.create_table(
        "model_definitions",
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("connection_id", sa.UUID(), nullable=False),
        sa.Column("vendor_model_id", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column(
            "capabilities",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "param_schema",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="active",
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["connection_id"], ["model_connections.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index(
        "ix_model_definitions_connection_id",
        "model_definitions",
        ["connection_id"],
        unique=False,
    )

    op.create_table(
        "runtime_config_versions",
        sa.Column("version_seq", sa.Integer(), nullable=False),
        sa.Column("planner_model_id", sa.UUID(), nullable=False),
        sa.Column("planner_connection_version_id", sa.UUID(), nullable=False),
        sa.Column("text_to_image_model_id", sa.UUID(), nullable=False),
        sa.Column("text_to_image_connection_version_id", sa.UUID(), nullable=False),
        sa.Column("image_edit_model_id", sa.UUID(), nullable=False),
        sa.Column("image_edit_connection_version_id", sa.UUID(), nullable=False),
        sa.Column(
            "runtime_params",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "test_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("published_by", sa.UUID(), nullable=False),
        sa.Column("rolled_back_from", sa.Integer(), nullable=True),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["planner_model_id"], ["model_definitions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["planner_connection_version_id"],
            ["model_connection_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["text_to_image_model_id"], ["model_definitions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["text_to_image_connection_version_id"],
            ["model_connection_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["image_edit_model_id"], ["model_definitions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["image_edit_connection_version_id"],
            ["model_connection_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["published_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version_seq"),
    )

    op.create_table(
        "runtime_config_state",
        sa.Column("current_version_id", sa.UUID(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["current_version_id"],
            ["runtime_config_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("runtime_config_state")
    op.drop_table("runtime_config_versions")
    op.drop_index("ix_model_definitions_connection_id", table_name="model_definitions")
    op.drop_table("model_definitions")
    op.drop_index(
        "ix_model_connection_versions_connection_id",
        table_name="model_connection_versions",
    )
    op.drop_table("model_connection_versions")
    op.drop_table("model_connections")