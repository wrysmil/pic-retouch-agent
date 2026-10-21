import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

from app.models import AgentRun
from app.models.tool_run import RunStatus
from app.tools import UnknownTool, label_of, spec_of

MAX_MESSAGE = 1000


class MessageIn(BaseModel):
    """一条自然语言修图指令。"""

    text: Annotated[str, Field(min_length=1, max_length=MAX_MESSAGE)]
    # 客户端生成的请求键：重复点击复用同一个键，服务端返回原轮次
    request_id: Annotated[str | None, Field(max_length=80)] = None

    @field_validator("text")
    @classmethod
    def _require_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("指令不能为空")
        return value


class PlanStepOut(BaseModel):
    """计划中的一步：调用哪个工具、依赖哪几步、当前状态与执行记录。"""

    id: str
    tool: str
    label: str
    depends_on: list[str] = []
    run_id: uuid.UUID | None = None
    status: str = "pending"
    # 该步预计消耗的 AI 图片次数；前端在确认按钮旁汇总展示
    units: int = 0

    @classmethod
    def of(cls, step: dict) -> "PlanStepOut":
        run_id = step.get("run_id")
        try:
            units = spec_of(step["tool"]).quota_units(step.get("params") or {})
        except UnknownTool:
            units = 0
        return cls(
            id=step.get("id") or step["tool"],
            tool=step["tool"],
            label=label_of(step["tool"], step.get("params")),
            depends_on=list(step.get("depends_on") or []),
            run_id=uuid.UUID(run_id) if run_id else None,
            # 老数据没有 status 字段：有 run_id 就当已完成，否则待执行
            status=step.get("status") or ("succeeded" if run_id else "pending"),
            units=units,
        )


class PlanDraftOut(BaseModel):
    """规划中的草稿步骤：未校验、无执行权限，只用于逐步给出反馈。"""

    call_index: int
    id: str
    tool: str
    label: str
    params: dict = {}
    state: str = "draft"


class TurnOut(BaseModel):
    """编辑页左栏的一轮问答。

    phase 是真实阶段；status 保留为旧客户端兼容投影。规划中 steps 为空，
    草稿放在 plan_draft。
    """

    id: uuid.UUID
    revision: int
    goal: str
    reply: str
    status: RunStatus
    phase: str = "completed"
    public_summary: str = ""
    plan_version: int = 0
    planning_attempt: int = 1
    last_event_seq: int = 0
    error: str | None
    created_at: datetime
    steps: list[PlanStepOut] = []
    plan_draft: list[PlanDraftOut] = []

    @classmethod
    def of(cls, turn: AgentRun) -> "TurnOut":
        return cls(
            id=turn.id,
            revision=turn.revision,
            goal=turn.goal,
            reply=turn.reply,
            status=turn.status,
            phase=getattr(turn, "phase", "completed"),
            public_summary=turn.public_summary or "",
            plan_version=turn.plan_version or 0,
            planning_attempt=turn.planning_attempt or 1,
            last_event_seq=turn.last_event_seq or 0,
            error=turn.error,
            created_at=turn.created_at,
            steps=[PlanStepOut.of(step) for step in turn.plan],
            plan_draft=[PlanDraftOut(**draft) for draft in (turn.plan_draft or [])],
        )