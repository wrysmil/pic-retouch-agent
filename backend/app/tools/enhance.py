from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.edits.split import already_split
from app.layers import BACKGROUND_LAYER_ID, LayerDocument, LayerKind
from app.models.asset import AssetKind, AssetSource
from app.models.tool_run import ToolRun
from app.providers import EditRequest
from app.ratios import Ratio, cover_size
from app.services import assets, runs
from app.services.runtime_provider import image_client_for_run
from app.tools.base import ToolSpec
from app.tools.context import document_of, flatten_session, require_session
from app.tools.quota_units import count_of, one
from app.tools.target import background_target, layer_image, write_layer_image


class ReplaceBackgroundIn(BaseModel):
    prompt: str = Field(min_length=1, max_length=500)
    count: int = Field(default=1, ge=1, le=4)
    negative_prompt: str | None = None


class ExpandCanvasIn(BaseModel):
    ratio: Ratio
    prompt: str = Field(default="自然延伸画面边缘，保持主体完整", max_length=500)


class UpscaleImageIn(BaseModel):
    scale: int = Field(default=2, ge=2, le=4)


async def _store(
    session: AsyncSession, run: ToolRun, images: list[bytes], *, adopt_first: bool
) -> dict:
    created = [
        await assets.create_from_bytes(
            session, run.user_id, data, AssetKind.GENERATED, AssetSource.TOOL
        )
        for data in images
    ]
    result: dict = {"asset_ids": [str(asset.id) for asset in created]}
    if adopt_first and created:
        result["adopt_asset_id"] = str(created[0].id)
    return result


async def _progress(session: AsyncSession, run: ToolRun, progress: int, stage: str) -> None:
    await runs.report(session, run, progress, stage)


def _layered(document: LayerDocument) -> bool:
    """已拆层或多于一张图像层：生成整图只上墙，不写回文档。"""
    if already_split(document):
        return True
    return sum(1 for layer in document.layers if layer.kind is LayerKind.IMAGE) > 1


async def replace_background_exec(session: AsyncSession, run: ToolRun) -> dict:
    """未拆层时把整图交给模型并写回画布；已拆层时生成的整图只进图片墙。

    已拆层的画布不能把生成结果写回背景层：喂给模型的是拍平图，结果里必然
    带着主体，再塞回背景层就等于主体被画了两遍。
    """

    record = await require_session(session, run)
    document = document_of(record)
    target = background_target(document)
    wall_only = _layered(document)
    await runs.report(session, run, 15, "读取背景")
    # 只有「背景层是唯一的图像层」时才喂背景层自己的像素，免得模型把主体一起重画
    if wall_only or target.id != BACKGROUND_LAYER_ID:
        source = await flatten_session(session, record)
    else:
        source = await layer_image(session, record, target)
    await runs.report(session, run, 30, "生成新背景")
    client = await image_client_for_run(session, run)
    images = await client.provider.edit(
        EditRequest(
            prompt=f"只替换背景，保持主体、光线和边缘不变。新背景：{run.params['prompt']}",
            image=source,
            count=run.params["count"],
            negative_prompt=run.params.get("negative_prompt"),
        ),
        on_progress=lambda progress, stage: _progress(session, run, progress, stage),
    )
    if run.params["count"] > 1 or wall_only:
        await runs.report(session, run, 95, "候选已加入图片墙，点选采用")
        return await _store(session, run, images, adopt_first=False)
    kind = AssetKind.BACKGROUND if target.id == BACKGROUND_LAYER_ID else AssetKind.GENERATED
    return await write_layer_image(session, run, record, target.id, images[0], kind)


async def expand_canvas_exec(session: AsyncSession, run: ToolRun) -> dict:
    record = await require_session(session, run)
    canvas = document_of(record)
    width, height = cover_size(canvas.width, canvas.height, Ratio(run.params["ratio"]))
    await runs.report(session, run, 15, "读取画布")
    source = await flatten_session(session, record)
    await runs.report(session, run, 30, "延伸画幅")
    client = await image_client_for_run(session, run)
    images = await client.provider.edit(
        EditRequest(prompt=run.params["prompt"], image=source, width=width, height=height),
        on_progress=lambda progress, stage: _progress(session, run, progress, stage),
    )
    return await _store(session, run, images, adopt_first=not _layered(canvas))


async def upscale_image_exec(session: AsyncSession, run: ToolRun) -> dict:
    """超分产出的是整图，已拆层时同样只上墙。"""

    record = await require_session(session, run)
    canvas = document_of(record)
    await runs.report(session, run, 15, "读取画布")
    source = await flatten_session(session, record)
    await runs.report(session, run, 30, "提升分辨率")
    client = await image_client_for_run(session, run)
    output = await client.provider.upscale(
        source,
        run.params["scale"],
        on_progress=lambda progress, stage: _progress(session, run, progress, stage),
    )
    return await _store(session, run, [output], adopt_first=not _layered(canvas))


REPLACE_BACKGROUND = ToolSpec(
    name="replace_background",
    label="换背景",
    description=(
        "按文字描述替换背景。未拆层时写回画布；已拆层时拍平生成整图只进图片墙。"
        "一次可出 1 到 4 张候选；多于一张时不自动上画布，用户点选图片墙采用。"
    ),
    params=ReplaceBackgroundIn,
    handler=replace_background_exec,
    queued=True,
    session_required=True,
    agent_hidden=("negative_prompt",),
    quota_units=count_of,
)

EXPAND_CANVAS = ToolSpec(
    name="expand_canvas",
    label="扩图",
    description="把当前画布扩展到指定比例，并自然补全新增区域。主体保持完整，不要裁切。",
    params=ExpandCanvasIn,
    handler=expand_canvas_exec,
    queued=True,
    session_required=True,
    quota_units=one,
)

UPSCALE_IMAGE = ToolSpec(
    name="upscale_image",
    label="超分",
    description="提高当前画布分辨率。scale 为 2 或 4，默认 2 倍。不要用它换内容或改构图。",
    params=UpscaleImageIn,
    handler=upscale_image_exec,
    queued=True,
    session_required=True,
    quota_units=one,
)
