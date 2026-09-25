import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field

from app.layers import LayerDocument
from app.models import EditHistory, EditSession
from app.schemas.asset import AssetOut

MAX_WALL_ASSETS = 12


class SessionCreateIn(BaseModel):
    """创建编辑会话的请求参数。"""

    current_asset_id: uuid.UUID = Field(
        description="当前正在编辑的素材 ID",
    )
    asset_ids: Annotated[
        list[uuid.UUID],
        Field(
            max_length=MAX_WALL_ASSETS,
            description=f"图墙素材 ID 列表，最多 {MAX_WALL_ASSETS} 张，包含当前编辑的素材及同批候选图",
        ),
    ] = []
    title: str | None = Field(
        default=None,
        description="会话标题，不指定则自动生成",
    )


class SessionPatchIn(BaseModel):
    """修改编辑会话的请求参数。"""

    title: str | None = Field(
        default=None,
        description="新的会话标题",
    )
    current_asset_id: uuid.UUID | None = Field(
        default=None,
        description="新的当前编辑素材 ID，用于切换当前正在编辑的图片",
    )


class SessionOut(BaseModel):
    id: uuid.UUID
    title: str
    revision: int
    original_asset_id: uuid.UUID
    current_asset_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    @classmethod
    def of(cls, record: EditSession) -> "SessionOut":
        return cls(
            id=record.id,
            title=record.title,
            revision=record.revision,
            original_asset_id=record.original_asset_id,
            current_asset_id=record.current_asset_id,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )


class SessionDetailOut(SessionOut):
    document: LayerDocument
    assets: list[AssetOut] = []

    @classmethod
    def of_detail(cls, record: EditSession, assets: list[AssetOut]) -> "SessionDetailOut":
        return cls(
            **SessionOut.of(record).model_dump(),
            document=LayerDocument.model_validate(record.document),
            assets=assets,
        )


class HistoryOut(BaseModel):
    seq: int
    action: str
    params: dict
    result: dict
    created_at: datetime

    @classmethod
    def of(cls, entry: EditHistory) -> "HistoryOut":
        return cls(
            seq=entry.seq,
            action=entry.action,
            params=entry.params,
            result=entry.result,
            created_at=entry.created_at,
        )