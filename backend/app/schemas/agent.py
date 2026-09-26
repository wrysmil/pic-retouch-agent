import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

from app.models import AgentRun
from app.models.tool_run import RunStatus
from app.tools import label_of

MAX_MESSAGE = 1000


class MessageIn(BaseModel):
    """一条自然语言修图指令。"""

    text: Annotated[str, Field(min_length=1, max_length=MAX_MESSAGE)]

    @field_validator("text")
    @classmethod
    def _require_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("指令不能为空")
        return value


class PlanStepOut(BaseModel):
    """计划中的一步：调用哪个工具、模型给出的中文说法、以及投递后的执行记录。"""

    tool: str
    label: str
    run_id: uuid.UUID | None = None

    @classmethod
    def of(cls, step: dict) -> "PlanStepOut":
        return cls(tool=step["tool"], label=label_of(step["tool"]), run_id=step.get("run_id"))


class TurnOut(BaseModel):
    """编辑页左栏的一轮问答。status 只反映规划是否成功，步骤进度在各步骤的 run 里。"""

    id: uuid.UUID
    revision: int
    goal: str
    reply: str
    status: RunStatus
    error: str | None
    created_at: datetime
    steps: list[PlanStepOut] = []

    @classmethod
    def of(cls, turn: AgentRun) -> "TurnOut":
        return cls(
            id=turn.id,
            revision=turn.revision,
            goal=turn.goal,
            reply=turn.reply,
            status=turn.status,
            error=turn.error,
            created_at=turn.created_at,
            steps=[PlanStepOut.of(step) for step in turn.plan],
        )