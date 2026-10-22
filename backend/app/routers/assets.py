"""
素材（Asset）相关接口。

提供图片素材的上传、列表查询和详情获取功能。
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from app.db import SessionDep
from app.deps import CurrentUser
from app.models.asset import AssetKind, AssetSource
from app.schemas.asset import AssetOut, LibraryGroupOut
from app.security.rate_limit import upload_rate_limit
from app.services import assets as asset_service
from app.services.assets import ORPHAN_TITLE
from app.services.images import MAX_FILE_BYTES, ImageRejected, probe_async

router = APIRouter(prefix="/assets", tags=["assets"])

_READ_CHUNK = 1024 * 1024


async def _read_limited(file: UploadFile) -> bytes:
    """分块读取上传内容，超限立即中断，避免超大请求整体驻留内存。"""
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(_READ_CHUNK):
        total += len(chunk)
        if total > MAX_FILE_BYTES:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "文件超过 20 MB 上限")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post(
    "",
    dependencies=[Depends(upload_rate_limit)],
    status_code=status.HTTP_201_CREATED,
    summary="上传素材",
    description="上传图片文件作为素材，支持 PNG/JPG/WebP，单文件不超过 20MB。",
)
async def upload(
    user: CurrentUser,
    session: SessionDep,
    file: Annotated[UploadFile, File(description="要上传的图片文件")],
) -> AssetOut:
    """
    上传图片素材。

    - **file**: 图片文件，支持 PNG、JPG、WebP 格式
    - **返回**: 创建成功的素材信息

    **可能错误**:
    - 413: 文件超过 20MB 上限
    - 422: 不支持的图片格式或文件损坏
    """
    data = await _read_limited(file)

    try:
        meta = await probe_async(data)
    except ImageRejected as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc

    asset = await asset_service.create_from_bytes(
        session, user.id, data, AssetKind.ORIGINAL, AssetSource.UPLOAD, meta
    )
    return AssetOut.of(asset)


@router.get(
    "",
    summary="获取素材列表",
    description="获取当前用户的素材列表，按创建时间倒序排列。",
)
async def list_assets(
    user: CurrentUser,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200, description="返回的最大数量")] = 50,
) -> list[AssetOut]:
    """
    获取当前用户的素材列表。

    - **limit**: 返回素材数量上限（1-200），默认 50
    - **返回**: 素材列表
    """
    records = await asset_service.list_for_user(session, user.id, limit)
    return [AssetOut.of(asset) for asset in records]


@router.get(
    "/library",
    summary="获取素材库",
    description="按编辑会话分组的素材列表，遮罩等中间产物不返回。",
)
async def list_library(
    user: CurrentUser,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200, description="返回的最大会话数")] = 50,
) -> list[LibraryGroupOut]:
    """
    获取创作页素材库。

    - **limit**: 参与分组的最大会话数（1-200），默认 50
    - **返回**: 按会话分组（session_id 为空即未归组）的素材列表
    """
    groups = await asset_service.library_for_user(session, user.id, limit)
    return [
        LibraryGroupOut(
            session_id=record.id if record else None,
            title=record.title if record else ORPHAN_TITLE,
            updated_at=record.updated_at if record else cover.created_at,
            cover=AssetOut.of(cover),
            assets=[AssetOut.of(asset) for asset in assets],
        )
        for record, cover, assets in groups
    ]


@router.get(
    "/{asset_id}",
    summary="获取素材详情",
    description="根据 ID 获取单个素材的详细信息，包括签名访问 URL。",
)
async def get_asset(
    asset_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> AssetOut:
    """
    获取指定素材的详细信息。

    - **asset_id**: 素材 UUID
    - **返回**: 素材详情

    **可能错误**:
    - 404: 素材不存在或不属于当前用户
    """
    asset = await asset_service.get_for_user(session, user.id, asset_id)
    if asset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "素材不存在")
    return AssetOut.of(asset)
