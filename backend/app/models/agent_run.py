import enum
import uuid

from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TIMESTAMPTZ, UUIDBase, enum_column
from app.models.tool_run import RunStatus


class AgentPhase(enum.StrEnum):
    """一轮对话的真实阶段。与 RunStatus 分开，避免 queued 同时表示待确认与排队。"""

    PLANNING = "planning"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"
    NEEDS_ATTENTION = "needs_attention"

    @property
    def is_terminal(self) -> bool:
        return self in {
            AgentPhase.COMPLETED,
            AgentPhase.FAILED,
            AgentPhase.CANCELED,
        }


class AgentRun(UUIDBase):
    """一轮自然语言指令的规划与执行进度，对应编辑页左栏的一次问答。

    plan 即断点：刷新或 worker 重启后按已落库的步骤状态继续。
    """

    __tablename__ = "agent_runs"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_turn_user_request"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("edit_sessions.id", ondelete="CASCADE"), index=True
    )
    # 规划所基于的修订号，用于判断执行时画布是否已被改动
    revision: Mapped[int]
    goal: Mapped[str] = mapped_column(Text)
    reply: Mapped[str] = mapped_column(Text, default="")
    plan: Mapped[list] = mapped_column(JSONB, default=list)
    status: Mapped[RunStatus] = mapped_column(enum_column(RunStatus))
    error: Mapped[str | None] = mapped_column(Text, default=None)
    # 锁定的运行模型配置版本 id；为空说明此轮早于发布机制，仍可继续完成
    runtime_config_version_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("runtime_config_versions.id", ondelete="RESTRICT"),
        default=None,
        index=True,
    )

    # 用户级请求幂等键：同键同文本返回原轮次，不再多建任务
    idempotency_key: Mapped[str | None] = mapped_column(String(80), default=None)
    phase: Mapped[AgentPhase] = mapped_column(
        enum_column(AgentPhase, length=32),
        default=AgentPhase.PLANNING,
        nullable=False,
        index=True,
    )
    # 规划尝试号；用户主动重新规划才递增，异常恢复沿用原值
    planning_attempt: Mapped[int] = mapped_column(default=1, nullable=False)
    # 公开草稿：只读展示，未校验，没有执行权限
    plan_draft: Mapped[list] = mapped_column(JSONB, default=list)
    # 可公开的阶段说明，不是模型内部思维链
    public_summary: Mapped[str] = mapped_column(Text, default="")
    plan_version: Mapped[int] = mapped_column(default=0, nullable=False)
    # 规划图 thread：turn:<id>:<attempt>；仅内部恢复使用
    checkpoint_thread_id: Mapped[str | None] = mapped_column(String(80), default=None)
    # 轮次事件游标；事件追加时条件自增，保证同一轮内 seq 连续
    last_event_seq: Mapped[int] = mapped_column(default=0, nullable=False)
    # 规划租约：worker 领取后写入，恢复扫描只捡过期或空租约的 planning 轮次
    planning_lease_until: Mapped[datetime | None] = mapped_column(
        TIMESTAMPTZ, default=None
    )