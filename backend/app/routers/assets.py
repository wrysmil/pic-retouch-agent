"""
素材（Asset）相关接口。

提供图片素材的上传、列表查询和详情获取功能。
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status

from app.db import SessionDep
from app.deps import CurrentUser
from app.models.asset import AssetKind, AssetSource
from app.schemas.asset import AssetOut
from app.services import assets as asset_service
from app.services.images import MAX_FILE_BYTES, ImageRejected, probe

router = APIRouter(prefix="/assets", tags=["assets"])


@router.post(
    "",
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
    data = await file.read()
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "文件超过 20 MB 上限")

    try:
        meta = probe(data)
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