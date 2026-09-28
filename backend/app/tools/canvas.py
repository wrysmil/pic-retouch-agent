from typing import Literal

from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.edits.document import EditError, crop, flip, reorder, rotate, scale, set_opacity
from app.layers import LayerMissing
from app.models import ToolRun
from app.ratios import Ratio
from app.tools.base import ToolSpec
from app.tools.context import ToolError, document_of, require_session


# 画布工具类

# 图层 ID 由服务端从会话上下文填入，模型不需要也不能指定
_LAYER = "layer_id"


class LayerRef(BaseModel):
    """图层类工具的公共入参，layer_id 为空表示作用于最上层图像。"""

    layer_id: str | None = None


class FlipIn(LayerRef):
    """翻转入参，direction 指翻转所在的轴而非旋转方向。"""

    direction: Literal["horizontal", "vertical"]


class OpacityIn(LayerRef):
    """透明度入参。"""

    opacity: float = Field(ge=0, le=1)


class ScaleIn(LayerRef):
    # 相对倍率与绝对缩放两套字段并存，兼容模型的不同表述
    factor: float | None = Field(default=None, gt=0, le=8)
    scale_x: float | None = Field(default=None, gt=0, le=8)
    scale_y: float | None = Field(default=None, gt=0, le=8)

    @model_validator(mode="after")
    def _need_target(self) -> "ScaleIn":
        if self.factor is None and self.scale_x is None and self.scale_y is None:
            raise ValueError("需要相对倍率或绝对缩放")
        return self


class RotateIn(LayerRef):
    # angle 为增量、rotation 为绝对值，两者取其一
    angle: float | None = Field(default=None, ge=-360, le=360)
    rotation: float | None = Field(default=None, ge=-360, le=360)

    @model_validator(mode="after")
    def _need_angle(self) -> "RotateIn":
        if self.angle is None and self.rotation is None:
            raise ValueError("需要旋转角度")
        return self


class ReorderIn(LayerRef):
    """层级调整入参，top/bottom 直接置顶置底，up/down 只移动一层。"""

    place: Literal["top", "bottom", "up", "down"]


class CropRect(BaseModel):
    """归一化裁剪框，取值 0 到 1，相对画布左上角。"""

    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def _inside(self) -> "CropRect":
        # 留一点容差，避免 0.3+0.7 这类浮点累加误差被误判为越界
        if self.x + self.width > 1.0001 or self.y + self.height > 1.0001:
            raise ValueError("裁剪框超出画布")
        return self


class CropIn(BaseModel):
    """按比例居中裁剪或按矩形裁剪，二选一。"""

    ratio: Ratio | None = None
    rect: CropRect | None = None

    @model_validator(mode="after")
    def _need_one(self) -> "CropIn":
        if (self.ratio is None) == (self.rect is None):
            raise ValueError("裁剪需要比例或裁剪框之一")
        return self


async def _apply(session: AsyncSession, run: ToolRun, mutate) -> dict:
    """画布类工具的统一外壳：取会话文档、执行纯函数变换、回传新文档。

    mutate 只接收文档和已校验的参数，图层不存在或变换非法统一转成 ToolError。
    """

    # require_session 用 run.session_id 查 edit_sessions 表，返回一条 EditSession 记录。
    # 这条记录里的 document 字段（edit_session.py:32）就是当前画布长什么样——只有一份!!!，最新的。
    record = await require_session(session, run)
    # 以上是读画布状态，record 拿到手的是一条数据库记录，里面装着一堆字段（title、revision、history_seq、document……）
    try:
        '''
run.params                        ①  {"layer_id": None, "factor": 2.0, ...}
record.document                   ②  {"width": 1920, "height": 1080, "layers": [...]}
        ↓ document_of(record)    ③  反序列化：dict → LayerDocument 对象
        ↓ mutate(doc, params)    ④  传入具体变换逻辑，返回新对象

        '''
        document = mutate(document_of(record), run.params)
    except (LayerMissing, EditError) as exc:
        raise ToolError(str(exc)) from exc
    return {"document": document.model_dump(mode="json")}


async def flip_layer(session: AsyncSession, run: ToolRun) -> dict:
    """水平或垂直翻转图层，未指定图层时翻转最上层图像。"""

    return await _apply(
        session,
        run,
        lambda doc, params: flip(doc, params.get(_LAYER), params["direction"]),
    )


async def set_layer_opacity(session: AsyncSession, run: ToolRun) -> dict:
    """设置图层不透明度，0 为全透明，1 为不透明。"""

    return await _apply(
        session,
        run,
        lambda doc, params: set_opacity(doc, params.get(_LAYER), params["opacity"]),
    )


async def scale_layer(session: AsyncSession, run: ToolRun) -> dict:
    """缩放图层，等比用 factor，独立指定 X/Y 用 scale_x / scale_y。"""

    return await _apply(
        session,
        run,
        lambda doc, params: scale(
            doc,
            params.get(_LAYER),
            factor=params.get("factor"),
            scale_x=params.get("scale_x"),
            scale_y=params.get("scale_y"),
        ),
    )


async def rotate_layer(session: AsyncSession, run: ToolRun) -> dict:
    """旋转图层，顺时针为正；angle 累加，rotation 直接设为绝对角度。"""

    return await _apply(
        session,
        run,
        lambda doc, params: rotate(
            doc,
            params.get(_LAYER),
            angle=params.get("angle"),
            rotation=params.get("rotation"),
        ),
    )


async def reorder_layer(session: AsyncSession, run: ToolRun) -> dict:
    """调整图层叠放次序，置顶、置底、上移一层或下移一层。"""

    return await _apply(
        session,
        run,
        lambda doc, params: reorder(doc, params.get(_LAYER), params["place"]),
    )


async def crop_canvas(session: AsyncSession, run: ToolRun) -> dict:
    """裁剪画布；只给 ratio 时按比例居中裁切，给 rect 时按矩形裁切。"""

    def mutate(doc, params):
        rect = params.get("rect")
        box = (rect["x"], rect["y"], rect["width"], rect["height"]) if rect else None
        ratio = Ratio(params["ratio"]) if params.get("ratio") else None
        return crop(doc, ratio=ratio, rect=box)

    return await _apply(session, run, mutate)


def _canvas(name: str, label: str, description: str, params, handler) -> ToolSpec:
    """构造画布类工具：全部同步执行，且必须绑定会话。"""

    return ToolSpec(
        name=name,
        label=label,
        description=description,
        params=params,
        handler=handler,
        # 只改图层文档、不耗算力，无需排队等待
        queued=False,
        session_required=True,
        agent_hidden=(_LAYER,),
    )


# 画布类工具清单，供工具注册表收录；description 是给模型看的，不写实现细节
CROP_CANVAS = _canvas(
    "crop_canvas",
    "裁剪",
    "按比例或归一化矩形裁切画布。只改图层文档，不调用生成模型。",
    CropIn,
    crop_canvas,
)
FLIP_LAYER = _canvas(
    "flip_layer",
    "翻转",
    "水平或垂直翻转指定图层，默认最上层图像。",
    FlipIn,
    flip_layer,
)
SET_LAYER_OPACITY = _canvas(
    "set_layer_opacity",
    "透明度",
    "设置图层透明度，取值 0 到 1。",
    OpacityIn,
    set_layer_opacity,
)
REORDER_LAYER = _canvas(
    "reorder_layer",
    "图层顺序",
    "调整图层前后顺序：top / bottom / up / down。",
    ReorderIn,
    reorder_layer,
)
SCALE_LAYER = _canvas(
    "scale_layer",
    "缩放",
    "缩放图层。factor 为相对倍率，scale_x / scale_y 为绝对值。",
    ScaleIn,
    scale_layer,
)
ROTATE_LAYER = _canvas(
    "rotate_layer",
    "旋转",
    "旋转图层。angle 为相对角度，rotation 为绝对角度，顺时针为正。",
    RotateIn,
    rotate_layer,
)