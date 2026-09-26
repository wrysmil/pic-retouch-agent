import uuid
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

from app.models.tool_run import RunStatus, ToolRun
from app.ratios import Ratio
from app.schemas.asset import AssetOut

MAX_PROMPT = 1500
MAX_REFERENCES = 3


class GenerateIn(BaseModel):
    """文生图请求参数。"""

    prompt: Annotated[
        str,
        Field(
            min_length=1,
            max_length=MAX_PROMPT,
            description="图片描述文本，用于指导模型生成图片的内容",
        ),
    ]
    ratio: Ratio = Field(
        default=Ratio.SQUARE,
        description="生成图片的宽高比例，如 '1:1'（正方形）、'16:9'（横向）、'9:16'（竖向）",
    )
    count: Annotated[int, Field(ge=1, le=6, description="生成图片数量，1-6 张")] = 4
    negative_prompt: Annotated[
        str | None,
        Field(
            max_length=MAX_PROMPT,
            description="负面提示词，描述不希望出现在图片中的元素",
        ),
    ] = None
    seed: Annotated[
        int | None,
        Field(
            ge=0,
            le=2147483647,
            description="随机种子，相同种子可复现相似结果，不指定则随机生成",
        ),
    ] = None
    reference_asset_ids: Annotated[
        list[uuid.UUID],
        Field(
            max_length=MAX_REFERENCES,
            description="参考图片 ID 列表，最多 3 张，用于风格/内容参考",
        ),
    ] = []

    @field_validator("prompt")
    @classmethod
    def _require_prompt(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("提示词不能为空")
        return value

    @field_validator("negative_prompt")
    @classmethod
    def _blank_to_none(cls, value: str | None) -> str | None:
        return value.strip() or None if value else None


class RunOut(BaseModel):
    id: uuid.UUID
    tool: str
    status: RunStatus
    progress: int
    stage: str
    error: str | None
    prompt: str | None = None
    session_id: uuid.UUID | None = None
    candidates: list[AssetOut] = []

    @classmethod
    def of(cls, run: ToolRun, candidates: list[AssetOut] | None = None) -> "RunOut":
        return cls(
            id=run.id,
            tool=run.tool,
            status=run.status,
            progress=run.progress,
            stage=run.stage,
            error=run.error,
            prompt=run.params.get("prompt"),
            session_id=run.session_id,
            candidates=candidates or [],
        )