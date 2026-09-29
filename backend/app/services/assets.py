"""
素材（Asset）服务层。

提供素材的创建、查询和归属校验功能。
素材上传后存储到对象存储，数据库仅存元信息和访问路径。
"""

import uuid
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import storage
from app.models import Asset, EditSession, SessionAsset
from app.models.asset import AssetKind, AssetSource
from app.services.images import ImageMeta, probe

# 遮罩、抠图层是会话内部产物，创作页历史素材不单独摊开
_WORKING = {AssetKind.MASK, AssetKind.SUBJECT, AssetKind.BACKGROUND}
ORPHAN_TITLE = "未归入会话"


def _storage_key(user_id: uuid.UUID, asset_id: uuid.UUID, extension: str) -> str:
    """生成素材在对象存储中的路径 key，格式：users/{user_id}/{asset_id}.{ext}"""
    return f"users/{user_id}/{asset_id}.{extension}"


async def create_from_bytes(
    session: AsyncSession,
    user_id: uuid.UUID,
    data: bytes,
    kind: AssetKind,
    source: AssetSource,
    meta: ImageMeta | None = None,
) -> Asset:
    """
    创建素材：校验图片、写入对象存储、落库。

    - **session**: 数据库会话
    - **user_id**: 素材归属的用户 ID
    - **data**: 图片二进制数据
    - **kind**: 素材类型（ORIGINAL=原图，GENERATED=生成图）
    - **source**: 来源（UPLOAD=上传，GENERATE=生成，EDIT=编辑）
    - **meta**: 图片元信息（可选，不传则自动探测）
    - **返回**: 创建的 Asset 记录
    """
    meta = meta or probe(data)
    asset_id = uuid.uuid4()
    key = _storage_key(user_id, asset_id, meta.extension)

    await storage.put(key, data, meta.content_type)

    asset = Asset(
        id=asset_id,
        user_id=user_id,
        kind=kind,
        source=source,
        storage_key=key,
        image_format=meta.image_format,
        width=meta.width,
        height=meta.height,
        size_bytes=meta.size_bytes,
        has_alpha=meta.has_alpha,
    )
    session.add(asset)
    await session.commit()
    return asset


async def list_for_user(session: AsyncSession, user_id: uuid.UUID, limit: int = 50) -> list[Asset]:
    """
    获取用户的素材列表。

    - **session**: 数据库会话
    - **user_id**: 用户 ID
    - **limit**: 返回数量上限，默认 50
    - **返回**: 按创建时间倒序的素材列表
    """
    result = await session.scalars(
        select(Asset).where(Asset.user_id == user_id).order_by(Asset.created_at.desc()).limit(limit)
    )
    return list(result)


async def get_for_user(
    session: AsyncSession, user_id: uuid.UUID, asset_id: uuid.UUID
) -> Asset | None:
    """
    按 ID 获取素材，并校验归属。

    - **session**: 数据库会话
    - **user_id**: 用户 ID（用于归属校验）
    - **asset_id**: 素材 ID
    - **返回**: 素材记录（不存在或不属于该用户返回 None）
    """
    return await session.scalar(select(Asset).where(Asset.id == asset_id, Asset.user_id == user_id))


def _visible(assets: list[Asset]) -> list[Asset]:
    return [asset for asset in assets if asset.kind not in _WORKING]


async def library_for_user(
    session: AsyncSession, user_id: uuid.UUID, limit: int = 50
) -> list[tuple[EditSession | None, Asset, list[Asset]]]:
    """创作页素材：按会话收拢成组，没进过会话的上传与生成图单独一组。

    返回 (会话, 封面, 组内素材) 三元组列表，会话为空即未归组。
    """
    records = list(
        await session.scalars(
            select(EditSession)
            .where(EditSession.user_id == user_id)
            .order_by(EditSession.updated_at.desc())
            .limit(limit)
        )
    )

    walls: dict[uuid.UUID, list[Asset]] = defaultdict(list)
    attached: set[uuid.UUID] = set()
    if records:
        rows = await session.execute(
            select(SessionAsset.session_id, Asset)
            .join(Asset, Asset.id == SessionAsset.asset_id)
            .where(SessionAsset.session_id.in_([record.id for record in records]))
            .order_by(SessionAsset.position)
        )
        for session_id, asset in rows:
            walls[session_id].append(asset)
            attached.add(asset.id)

    cover_ids = {record.current_asset_id for record in records}
    covers = {}
    if cover_ids:
        covers = {
            asset.id: asset
            for asset in await session.scalars(select(Asset).where(Asset.id.in_(cover_ids)))
        }

    groups: list[tuple[EditSession | None, Asset, list[Asset]]] = []
    for record in records:
        visible = _visible(walls.get(record.id, []))
        # 当前图本身可能被过滤掉（它是主体层产物），这时退回组内第一张
        cover = covers.get(record.current_asset_id) or (visible[0] if visible else None)
        if cover is None:
            continue
        groups.append((record, cover, visible or [cover]))

    leftover = list(
        await session.scalars(
            select(Asset)
            .where(
                Asset.user_id == user_id,
                Asset.kind.notin_(_WORKING),
                *([Asset.id.notin_(attached)] if attached else []),
            )
            .order_by(Asset.created_at.desc())
            .limit(limit)
        )
    )
    if leftover:
        groups.append((None, leftover[0], leftover))
    return groups