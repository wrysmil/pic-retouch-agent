"""membership quota

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def _enum(*values: str, name: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=False, length=16)


def upgrade() -> None:
    op.create_table(
        "membership_policy_versions",
        sa.Column("member_type", _enum("free", "vip", name="membershiptype"), nullable=False),
        sa.Column("version_seq", sa.Integer(), nullable=False),
        sa.Column("daily_limit", sa.Integer(), nullable=False),
        sa.Column("counting_unit", sa.String(length=32), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("features", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("published_by", sa.UUID(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["published_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("member_type", "effective_from", name="uq_policy_type_effective"),
        sa.UniqueConstraint("member_type", "version_seq", name="uq_policy_type_seq"),
    )

    op.create_table(
        "quota_buckets",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("quota_date", sa.Date(), nullable=False),
        sa.Column("policy_version_id", sa.UUID(), nullable=False),
        sa.Column("limit", sa.Integer(), nullable=False),
        sa.Column("adjustment", sa.Integer(), nullable=False),
        sa.Column("reserved", sa.Integer(), nullable=False),
        sa.Column("consumed", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["policy_version_id"], ["membership_policy_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "quota_date", name="uq_bucket_user_date"),
    )
    op.create_index(op.f("ix_quota_buckets_user_id"), "quota_buckets", ["user_id"], unique=False)

    op.create_table(
        "quota_reservations",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("bucket_id", sa.UUID(), nullable=False),
        sa.Column("policy_version_id", sa.UUID(), nullable=False),
        sa.Column("logical_key", sa.String(length=160), nullable=False),
        sa.Column("units", sa.Integer(), nullable=False),
        sa.Column("settled", sa.Integer(), nullable=False),
        sa.Column("released", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            _enum("reserved", "settled", "released", "unknown", name="reservationstatus"),
            nullable=False,
        ),
        sa.Column("run_id", sa.UUID(), nullable=True),
        sa.Column("turn_id", sa.UUID(), nullable=True),
        sa.Column("step_id", sa.String(length=32), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["bucket_id"], ["quota_buckets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["policy_version_id"], ["membership_policy_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["run_id"], ["tool_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["turn_id"], ["agent_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "logical_key", name="uq_reservation_key"),
    )
    op.create_index(op.f("ix_quota_reservations_user_id"), "quota_reservations", ["user_id"], unique=False)
    op.create_index(op.f("ix_quota_reservations_bucket_id"), "quota_reservations", ["bucket_id"], unique=False)
    op.create_index(op.f("ix_quota_reservations_run_id"), "quota_reservations", ["run_id"], unique=False)

    op.create_table(
        "quota_ledger",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("bucket_id", sa.UUID(), nullable=False),
        sa.Column("reservation_id", sa.UUID(), nullable=True),
        sa.Column(
            "action",
            _enum("reserve", "consume", "release", "adjust", name="ledgeraction"),
            nullable=False,
        ),
        sa.Column("units", sa.Integer(), nullable=False),
        sa.Column("available_after", sa.Integer(), nullable=False),
        sa.Column("operator_id", sa.UUID(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=200), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["bucket_id"], ["quota_buckets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["operator_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reservation_id"], ["quota_reservations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(op.f("ix_quota_ledger_user_id"), "quota_ledger", ["user_id"], unique=False)
    op.create_index(op.f("ix_quota_ledger_bucket_id"), "quota_ledger", ["bucket_id"], unique=False)

    op.create_table(
        "image_call_attempts",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("tool", sa.String(length=48), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=True),
        sa.Column("reservation_id", sa.UUID(), nullable=True),
        sa.Column("logical_unit", sa.String(length=160), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("provider_request_id", sa.String(length=128), nullable=True),
        sa.Column(
            "send_state",
            _enum("not_sent", "sent", "succeeded", "failed", "unknown", name="callstate"),
            nullable=False,
        ),
        sa.Column("output_asset_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["reservation_id"], ["quota_reservations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["run_id"], ["tool_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_image_call_attempts_user_id"), "image_call_attempts", ["user_id"], unique=False)
    op.create_index(op.f("ix_image_call_attempts_run_id"), "image_call_attempts", ["run_id"], unique=False)

    # 默认免费策略：开发值 5 次/日。生产值由后台发布新版本覆盖。
    op.execute(
        """
        INSERT INTO membership_policy_versions
            (id, member_type, version_seq, daily_limit, counting_unit, timezone,
             features, effective_from, published_by, note)
        VALUES
            (gen_random_uuid(), 'free', 1, 5, 'image', 'Asia/Shanghai',
             '{"vip": "coming_soon"}'::jsonb, DATE '2026-01-01', NULL, '迁移种子：免费会员每日 5 次')
        """
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_image_call_attempts_run_id"), table_name="image_call_attempts")
    op.drop_index(op.f("ix_image_call_attempts_user_id"), table_name="image_call_attempts")
    op.drop_table("image_call_attempts")
    op.drop_index(op.f("ix_quota_ledger_bucket_id"), table_name="quota_ledger")
    op.drop_index(op.f("ix_quota_ledger_user_id"), table_name="quota_ledger")
    op.drop_table("quota_ledger")
    op.drop_index(op.f("ix_quota_reservations_run_id"), table_name="quota_reservations")
    op.drop_index(op.f("ix_quota_reservations_bucket_id"), table_name="quota_reservations")
    op.drop_index(op.f("ix_quota_reservations_user_id"), table_name="quota_reservations")
    op.drop_table("quota_reservations")
    op.drop_index(op.f("ix_quota_buckets_user_id"), table_name="quota_buckets")
    op.drop_table("quota_buckets")
    op.drop_table("membership_policy_versions")
