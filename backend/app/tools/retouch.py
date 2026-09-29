import asyncio

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.edits.pixels import adjust, remove_background
from app.layers import resolve_layer
from app.models.asset import AssetKind
from app.models.tool_run import ToolRun
from app.services import runs
from app.tools.base import ToolSpec
from app.tools.context import document_of, require_session
from app.tools.target import layer_image, write_layer_image

# 图层 ID 由界面从选中项填入，模型不需要也不能指定
_LAYER = "layer_id"


class RemoveBackgroundIn(BaseModel):
    layer_id: str | None = None


class AdjustIn(BaseModel):
    """调色参数；除晕影外均为 -1 到 1，默认 0 表示这一项不动。"""

    layer_id: str | None = None
    brightness: float = Field(default=0, ge=-1, le=1)
    contrast: float = Field(default=0, ge=-1, le=1)
    highlights: float = Field(default=0, ge=-1, le=1)
    shadows: float = Field(default=0, ge=-1, le=1)
    temperature: float = Field(default=0, ge=-1, le=1)
    tint: float = Field(default=0, ge=-1, le=1)
    saturation: float = Field(default=0, ge=-1, le=1)
    vibrance: float = Field(default=0, ge=-1, le=1)
    sharpness: float = Field(default=0, ge=-1, le=1)
    clarity: float = Field(default=0, ge=-1, le=1)
    # 晕影只有加深一档，没有反向，取值 0 到 1
    vignette: float = Field(default=0, ge=0, le=1)


async def remove_background_exec(session: AsyncSession, run: ToolRun) -> dict:
    """识别指定图层的主体并输出透明 PNG：读图层 → 抠图 → 写回该层。"""

    record = await require_session(session, run)
    layer = resolve_layer(document_of(record), run.params.get(_LAYER))
    await runs.report(session, run, 20, "识别主体")
    data = await layer_image(session, record, layer)
    await runs.report(session, run, 50, "去除背景")
    # 纯 CPU 计算，放到线程池，别占着事件循环
    output = await asyncio.to_thread(remove_background, data)
    return await write_layer_image(session, run, record, layer.id, output, AssetKind.SUBJECT)


async def adjust_image_exec(session: AsyncSession, run: ToolRun) -> dict:
    """按参数调整指定图层的色调；未提到的参数保持原样。"""

    record = await require_session(session, run)
    layer = resolve_layer(document_of(record), run.params.get(_LAYER))
    await runs.report(session, run, 20, "读取图层")
    # 直接读图层自己的 PNG，透明通道天然就在，不用再拍平一次
    data = await layer_image(session, record, layer)
    # 只传非 0 的调色项，layer_id 不是调色参数必须排除
    params = {key: value for key, value in run.params.items() if value and key != _LAYER}
    await runs.report(session, run, 60, "调整色彩")
    output = await asyncio.to_thread(lambda: adjust(data, **params))
    return await write_layer_image(session, run, record, layer.id, output, AssetKind.GENERATED)


REMOVE_BACKGROUND = ToolSpec(
    name="remove_background",
    label="去背景",
    description="识别当前图层的主体并去掉背景。默认最上层图像。不要用它来换背景或生成新画面。",
    params=RemoveBackgroundIn,
    handler=remove_background_exec,
    queued=True,
    session_required=True,
    agent_hidden=(_LAYER,),
)

ADJUST_IMAGE = ToolSpec(
    name="adjust_image",
    label="调色",
    description=(
        "调整指定图层的亮度、对比度、高光、阴影、色温、色调、饱和度、自然饱和度、锐化、清晰度和晕影。"
        "默认最上层图像。参数取值 -1 到 1，晕影为 0 到 1。未提到的参数保持 0。"
    ),
    params=AdjustIn,
    handler=adjust_image_exec,
    queued=True,
    session_required=True,
    agent_hidden=(_LAYER,),
)
