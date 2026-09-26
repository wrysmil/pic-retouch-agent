"""
编辑会话服务层。

提供会话的创建、查询、修改和历史记录功能。
会话包含当前编辑的素材（图墙）和编辑历史。
"""

import uuid
from collections.abc import Iterable

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.layers import document_of
from app.models import Asset, EditHistory, EditSession, SessionAsset
from app.models.edit_history import HISTORY_LIMIT

# 标题长度限制
TITLE_LIMIT = 80
# 默认会话标题
DEFAULT_TITLE = "未命名会话"


class SessionNotFound(Exception):
    """会话不存在或无权访问"""

    pass


def normalize_title(text: str | None) -> str:
    """
    规范化会话标题。

    - **text**: 原始标题
    - **返回**: 去除首尾空白、合并中间空格、截断到 80 字符
    """
    cleaned = " ".join((text or "").split())
    return cleaned[:TITLE_LIMIT] or DEFAULT_TITLE


async def _next_position(session: AsyncSession, session_id: uuid.UUID) -> int:
    """获取会话中下一个素材的 position 值"""
    last = await session.scalar(
        select(func.max(SessionAsset.position)).where(SessionAsset.session_id == session_id)
    )
    return (last or 0) + 1


async def _attach(session: AsyncSession, record: EditSession, assets: Iterable[Asset]) -> None:
    """
    内部方法：将素材关联到会话。

    - **session**: 数据库会话
    - **record**: 会话记录
    - **assets**: 要关联的素材列表
    - **效果**: 跳过已关联的素材，为新素材创建关联记录
    """
    known = set(
        await session.scalars(
            select(SessionAsset.asset_id).where(SessionAsset.session_id == record.id)
        )
    )
    position = await _next_position(session, record.id)

    for asset in assets:
        if asset.id in known:
            continue
        session.add(SessionAsset(session_id=record.id, asset_id=asset.id, position=position))
        known.add(asset.id)
        position += 1


async def _append_history(
    session: AsyncSession, record: EditSession, action: str, params: dict, result: dict
) -> None:
    """
    内部方法：追加编辑历史。

    - **session**: 数据库会话
    - **record**: 会话记录
    - **action**: 操作类型（如 "create_session"、"switch_current"）
    - **params**: 操作参数
    - **result**: 操作结果
    - **效果**: 创建历史记录，自动清理超出限制的旧记录
    """
    last = await session.scalar(
        select(func.max(EditHistory.seq)).where(EditHistory.session_id == record.id)
    )
    seq = (last or 0) + 1
    session.add(
        EditHistory(
            user_id=record.user_id,
            session_id=record.id,
            seq=seq,
            action=action,
            params=params,
            result=result,
        )
    )
    await session.execute(
        delete(EditHistory).where(
            EditHistory.session_id == record.id, EditHistory.seq <= seq - HISTORY_LIMIT
        )
    )


async def create(
    session: AsyncSession,
    user_id: uuid.UUID,
    current: Asset,
    wall: Iterable[Asset] = (),
    title: str | None = None,
) -> EditSession:
    """
    创建新的编辑会话。

    - **session**: 数据库会话
    - **user_id**: 用户 ID
    - **current**: 当前编辑的素材
    - **wall**: 图墙素材列表（与 current 共同存入）
    - **title**: 会话标题（可选）
    - **返回**: 创建的会话记录
    """
    record = EditSession(
        user_id=user_id,
        title=normalize_title(title),
        original_asset_id=current.id,
        current_asset_id=current.id,
        document=document_of(current).model_dump(mode="json"),
    )
    session.add(record)
    await session.flush()

    await _attach(session, record, [current, *wall])
    await _append_history(session, record, "create_session", {}, {"asset_id": str(current.id)})
    await session.commit()
    await session.refresh(record)
    return record


async def get_for_user(
    session: AsyncSession, session_id: uuid.UUID, user_id: uuid.UUID
) -> EditSession:
    """
    按 ID 获取会话，并校验归属。

    - **session**: 数据库会话
    - **session_id**: 会话 ID
    - **user_id**: 用户 ID（用于归属校验）
    - **返回**: 会话记录
    - **抛出**: SessionNotFound 不存在或无权访问
    """
    record = await session.scalar(
        select(EditSession).where(EditSession.id == session_id, EditSession.user_id == user_id)
    )
    if record is None:
        raise SessionNotFound
    return record


async def load(session: AsyncSession, session_id: uuid.UUID) -> EditSession:
    """
    不带用户过滤的读取，仅供已确认归属的后台任务使用。

    - **session**: 数据库会话
    - **session_id**: 会话 ID
    - **返回**: 会话记录
    - **抛出**: SessionNotFound 不存在
    """
    record = await session.get(EditSession, session_id)
    if record is None:
        raise SessionNotFound
    return record


async def list_for_user(
    session: AsyncSession, user_id: uuid.UUID, limit: int = 50
) -> list[EditSession]:
    """
    获取用户的会话列表。

    - **session**: 数据库会话
    - **user_id**: 用户 ID
    - **limit**: 返回数量上限，默认 50
    - **返回**: 按更新时间倒序的会话列表
    """
    result = await session.scalars(
        select(EditSession)
        .where(EditSession.user_id == user_id)
        .order_by(EditSession.updated_at.desc())
        .limit(limit)
    )
    return list(result)


async def assets_of(session: AsyncSession, record: EditSession) -> list[Asset]:
    """
    获取会话关联的素材（图墙）。

    - **session**: 数据库会话
    - **record**: 会话记录
    - **返回**: 按 position 排序的素材列表
    """
    result = await session.scalars(
        select(Asset)
        .join(SessionAsset, SessionAsset.asset_id == Asset.id)
        .where(SessionAsset.session_id == record.id)
        .order_by(SessionAsset.position)
    )
    return list(result)


async def history_of(session: AsyncSession, record: EditSession) -> list[EditHistory]:
    """
    获取会话的编辑历史。

    - **session**: 数据库会话
    - **record**: 会话记录
    - **返回**: 按 seq 倒序的历史记录列表
    """
    result = await session.scalars(
        select(EditHistory)
        .where(EditHistory.session_id == record.id)
        .order_by(EditHistory.seq.desc())
    )
    return list(result)


async def attach(session: AsyncSession, record: EditSession, assets: Iterable[Asset]) -> None:
    """
    将素材关联到会话。

    - **session**: 数据库会话
    - **record**: 会话记录
    - **assets**: 要关联的素材列表
    """
    await _attach(session, record, assets)
    await session.commit()


async def record_result(
    session: AsyncSession,
    record: EditSession,
    assets: Iterable[Asset],
    action: str,
    params: dict,
    result: dict,
) -> None:
    """
    工具产出并入图片墙并留下编辑记录。不改当前图，采用与否交给用户。

    - **session**: 数据库会话
    - **record**: 会话记录
    - **assets**: 工具产出的素材列表
    - **action**: 工具名
    - **params**: 工具参数
    - **result**: 工具结果
    """
    await _attach(session, record, assets)
    await _append_history(session, record, action, params, result)
    await session.commit()


async def rename(session: AsyncSession, record: EditSession, title: str) -> EditSession:
    """
    重命名会话。

    - **session**: 数据库会话
    - **record**: 会话记录
    - **title**: 新标题
    - **返回**: 更新后的会话记录
    """
    record.title = normalize_title(title)
    await session.commit()
    await session.refresh(record)
    return record


async def switch_current(session: AsyncSession, record: EditSession, asset: Asset) -> EditSession:
    """
    切换会话的当前编辑素材。

    - **session**: 数据库会话
    - **record**: 会话记录
    - **asset**: 新的当前素材
    - **返回**: 更新后的会话记录
    - **效果**: 更新 current_asset_id，递增 revision，重置 document，记录历史
    """
    if record.current_asset_id != asset.id:
        record.current_asset_id = asset.id
        record.revision += 1
        record.document = document_of(asset).model_dump(mode="json")
        await _attach(session, record, [asset])
        await _append_history(
            session,
            record,
            "switch_current",
            {"asset_id": str(asset.id)},
            {"revision": record.revision},
        )
    await session.commit()
    await session.refresh(record)
    return record