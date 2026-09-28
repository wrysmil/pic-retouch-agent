import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app import storage
from app.edits.render import flatten
from app.layers import LayerDocument
from app.models import EditSession, ToolRun
from app.services import assets, sessions


class ToolError(Exception):
    """可直接展示给用户的工具失败。"""


async def require_session(session: AsyncSession, run: ToolRun) -> EditSession:
    """凭 run.session_id 取出当前编辑会话。

    画布类和像素类工具都要先调它拿会话：前者从 record.document 取画布文档，
    后者还要取 user_id 去读素材。没有会话就没有「当前画布」，两种情况都算失败。

    这里与 submit() 投递前的 session_required 检查重复，是有意为之：
    像素类工具异步执行，session_id 是 worker 从数据库读出来的，
    投递时那次校验拦不住执行期，只能在这里兜底。
    """

    if run.session_id is None:
        raise ToolError("此工具需要在编辑会话中使用")
    try:
        return await sessions.load(session, run.session_id)
    except sessions.SessionNotFound as exc:
        raise ToolError("会话不存在") from exc


def document_of(record: EditSession) -> LayerDocument:
    """从会话记录取出画布文档。

    库里存的是 JSONB，取出来是普通 dict，业务代码要的是能改属性的对象，
    所以每次都用 LayerDocument 的定义反序列化一遍，顺带做类型校验。
    """
    return LayerDocument.model_validate(record.document)


async def flatten_session(session: AsyncSession, record: EditSession) -> bytes:
    """把多层的画布合成一张 PNG，交给像素工具处理。

    画布类工具不用它——只改文档里的数字，不碰像素，所以能毫秒级返回；
    像素工具只认一张图，不认图层，必须先拍平才能抠图、调色。

    两步：先按文档收集每层的素材字节，再交给 render.flatten() 从底往上合成。
    文字、形状这类没有 asset_id 的图层，以及取不到素材的层，都直接跳过。
    """
    document = document_of(record)
    images: dict[uuid.UUID, bytes] = {}
    for layer in document.layers:
        if layer.asset_id is None:
            continue
        # get_for_user 顺带做权限校验，不能拿到任意 asset_id 就去读素材
        asset = await assets.get_for_user(session, record.user_id, layer.asset_id)
        if asset is None:
            continue
        images[asset.id] = await storage.get(asset.storage_key)
    return flatten(document, images)