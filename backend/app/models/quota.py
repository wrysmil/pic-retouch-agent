"""免费会员额度域模型。

日桶保存当天可用额度，预占与流水独立成表：users 上不存一个可随意覆盖的
「剩余次数」，所有变更都必须留下可对账的 QuotaLedger。
"""

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TIMESTAMPTZ, UUIDBase, enum_column


class MembershipType(enum.StrEnum):
    FREE = "free"
    # 预留：本期只解析为 free，不保存可生效的 VIP 套餐
    VIP = "vip"


class ReservationStatus(enum.StrEnum):
    RESERVED = "reserved"
    SETTLED = "settled"
    RELEASED = "released"
    # 外部请求已发出但结果未知：预占保留，等待人工或恢复协调器核对
    UNKNOWN = "unknown"


class LedgerAction(enum.StrEnum):
    RESERVE = "reserve"
    CONSUME = "consume"
    RELEASE = "release"
    ADJUST = "adjust"


class CallState(enum.StrEnum):
    NOT_SENT = "not_sent"
    SENT = "sent"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    UNKNOWN = "unknown"


class MembershipPolicyVersion(UUIDBase):
    """不可变的免费权益规则版本。日桶创建时复制上限与规则版本。"""

    __tablename__ = "membership_policy_versions"
    __table_args__ = (
        UniqueConstraint("member_type", "version_seq", name="uq_policy_type_seq"),
        UniqueConstraint("member_type", "effective_from", name="uq_policy_type_effective"),
    )

    member_type: Mapped[MembershipType] = mapped_column(
        enum_column(MembershipType), default=MembershipType.FREE, nullable=False
    )
    version_seq: Mapped[int] = mapped_column(nullable=False)
    daily_limit: Mapped[int] = mapped_column(nullable=False)
    counting_unit: Mapped[str] = mapped_column(String(32), default="image", nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Shanghai", nullable=False)
    # 能力限制、并发/频率等扩展项；首期只放展示需要的键
    features: Mapped[dict] = mapped_column(JSONB, default=dict)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    published_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    note: Mapped[str | None] = mapped_column(Text, default=None)


class QuotaBucket(UUIDBase):
    """一个用户在一个自然日的额度桶。首次使用时按当日生效策略创建。"""

    __tablename__ = "quota_buckets"
    __table_args__ = (UniqueConstraint("user_id", "quota_date", name="uq_bucket_user_date"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    quota_date: Mapped[date] = mapped_column(Date, nullable=False)
    policy_version_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("membership_policy_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    limit: Mapped[int] = mapped_column(default=0, nullable=False)
    adjustment: Mapped[int] = mapped_column(default=0, nullable=False)
    reserved: Mapped[int] = mapped_column(default=0, nullable=False)
    consumed: Mapped[int] = mapped_column(default=0, nullable=False)

    @property
    def available(self) -> int:
        return self.limit + self.adjustment - self.reserved - self.consumed


class QuotaReservation(UUIDBase):
    """一次逻辑 AI 消费单元的预占。

    logical_key 由调用方生成并保证稳定：同一业务重试复用原键，不会重复占额度；
    原预占释放后用户显式重试，应使用新的键（新的预占代数）。
    """

    __tablename__ = "quota_reservations"
    __table_args__ = (UniqueConstraint("user_id", "logical_key", name="uq_reservation_key"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    bucket_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("quota_buckets.id", ondelete="CASCADE"), index=True
    )
    policy_version_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("membership_policy_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    logical_key: Mapped[str] = mapped_column(String(160), nullable=False)
    units: Mapped[int] = mapped_column(nullable=False)
    settled: Mapped[int] = mapped_column(default=0, nullable=False)
    released: Mapped[int] = mapped_column(default=0, nullable=False)
    status: Mapped[ReservationStatus] = mapped_column(
        enum_column(ReservationStatus), default=ReservationStatus.RESERVED, nullable=False
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tool_runs.id", ondelete="SET NULL"), default=None, index=True
    )
    turn_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="SET NULL"), default=None
    )
    step_id: Mapped[str | None] = mapped_column(String(32), default=None)
    # 结果未知的预占超过该时间后进入待人工核查；不是自动释放时间
    expires_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, default=None)


class QuotaLedger(UUIDBase):
    """不可变额度流水。每次 reserve/consume/release/adjust 各写一行。"""

    __tablename__ = "quota_ledger"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    bucket_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("quota_buckets.id", ondelete="CASCADE"), index=True
    )
    reservation_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("quota_reservations.id", ondelete="SET NULL"), default=None
    )
    action: Mapped[LedgerAction] = mapped_column(enum_column(LedgerAction), nullable=False)
    units: Mapped[int] = mapped_column(nullable=False)
    # 本次变更后的 available，便于人工核对，不参与余额计算
    available_after: Mapped[int] = mapped_column(nullable=False)
    operator_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    reason: Mapped[str | None] = mapped_column(Text, default=None)
    idempotency_key: Mapped[str | None] = mapped_column(
        String(200), unique=True, default=None
    )


class ImageCallAttempt(UUIDBase):
    """一次外部图片调用尝试。与额度预占共用同一套任务/步骤关联，便于对账。"""

    __tablename__ = "image_call_attempts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    tool: Mapped[str] = mapped_column(String(48), nullable=False)
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tool_runs.id", ondelete="SET NULL"), default=None, index=True
    )
    reservation_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("quota_reservations.id", ondelete="SET NULL"), default=None
    )
    logical_unit: Mapped[str] = mapped_column(String(160), nullable=False)
    attempt: Mapped[int] = mapped_column(default=1, nullable=False)
    provider_request_id: Mapped[str | None] = mapped_column(String(128), default=None)
    send_state: Mapped[CallState] = mapped_column(
        enum_column(CallState), default=CallState.NOT_SENT, nullable=False
    )
    output_asset_ids: Mapped[list] = mapped_column(JSONB, default=list)
    error: Mapped[str | None] = mapped_column(Text, default=None)
