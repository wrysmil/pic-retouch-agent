import enum
import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TIMESTAMPTZ, UUIDBase, enum_column


class RunStatus(enum.StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"

    @property
    def is_terminal(self) -> bool:
        return self in {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELED}


class ToolRun(UUIDBase):
    """单次工具调用的执行记录。run id 同时作为队列任务 ID，重复投递不会重复执行。"""

    __tablename__ = "tool_runs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # 从创作页直接发起生成时还没有会话，产出图片届时不进任何图片墙
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("edit_sessions.id", ondelete="CASCADE"), default=None
    )
    tool: Mapped[str] = mapped_column(String(48))
    status: Mapped[RunStatus] = mapped_column(enum_column(RunStatus), default=RunStatus.QUEUED)
    progress: Mapped[int] = mapped_column(default=0)
    stage: Mapped[str] = mapped_column(String(64), default="")
    params: Mapped[dict] = mapped_column(JSONB, default=dict)
    result: Mapped[dict] = mapped_column(JSONB, default=dict)
    error: Mapped[str | None] = mapped_column(Text, default=None)
    retries: Mapped[int] = mapped_column(default=0)
    started_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, default=None)
    finished_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, default=None)
    # 绑定的运行模型配置版本：调度时由 submit/任务上下文固定；为空说明此任务早于发布机制
    runtime_config_version_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("runtime_config_versions.id", ondelete="RESTRICT"),
        default=None,
        index=True,
    )
    # 属于哪一轮 Agent 计划的哪一步；直接关联后不再靠扫描最近 20 轮反查
    turn_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="SET NULL"), default=None, index=True
    )
    step_id: Mapped[str | None] = mapped_column(String(32), default=None)
    attempt: Mapped[int] = mapped_column(default=1, nullable=False)