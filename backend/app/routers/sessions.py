"""
编辑会话相关接口。

提供图片编辑会话的创建、查询、修改和历史记录功能。
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionDep
from app.deps import CurrentUser
from app.models import Asset, EditSession, User
from app.schemas.agent import MessageIn, TurnOut
from app.schemas.asset import AssetOut
from app.schemas.session import (
    HistoryOut,
    SessionCreateIn,
    SessionDetailOut,
    SessionOut,
    SessionPatchIn,
)
from app.services import agent as agent_service
from app.services import assets as asset_service
from app.services import sessions
from app.services.sessions import SessionNotFound

router = APIRouter(prefix="/sessions", tags=["sessions"])


async def _asset(session: AsyncSession, user: User, asset_id: uuid.UUID) -> Asset:
    """获取素材并校验归属。"""
    asset = await asset_service.get_for_user(session, user.id, asset_id)
    if asset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "素材不存在")
    return asset


async def _load(session: AsyncSession, user: User, session_id: uuid.UUID) -> EditSession:
    """加载会话并校验归属。"""
    try:
        return await sessions.get_for_user(session, session_id, user.id)
    except SessionNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在") from exc


async def _detail(session: AsyncSession, record: EditSession) -> SessionDetailOut:
    """构建会话详情响应（含图墙）。"""
    wall = await sessions.assets_of(session, record)
    return SessionDetailOut.of_detail(record, [AssetOut.of(asset) for asset in wall])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="创建编辑会话",
    description="创建一个新的图片编辑会话，指定当前编辑的素材和图墙。",
)
async def create_session(
    payload: SessionCreateIn,
    user: CurrentUser,
    session: SessionDep,
) -> SessionDetailOut:
    """
    创建编辑会话。

    **请求参数 (SessionCreateIn)**:
    - **current_asset_id**: 当前正在编辑的素材 ID（必填）
    - **asset_ids**: 图墙素材 ID 列表，最多 12 张，包含当前编辑的素材及同批候选图（可选）
    - **title**: 会话标题，不指定则自动生成（可选）

    **返回**: 创建的会话详情（SessionDetailOut）

    **可能错误**:
    - 404: 指定素材不存在
    """
    current = await _asset(session, user, payload.current_asset_id)
    wall = [
        await _asset(session, user, asset_id)
        for asset_id in payload.asset_ids
        if asset_id != current.id
    ]

    record = await sessions.create(session, user.id, current, wall, payload.title)
    return await _detail(session, record)


@router.get(
    "",
    summary="获取会话列表",
    description="获取当前用户的编辑会话列表，按更新时间倒序排列。",
)
async def list_sessions(
    user: CurrentUser,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200, description="返回的最大数量")] = 50,
) -> list[SessionOut]:
    """
    获取会话列表。

    - **limit**: 返回会话数量上限（1-200），默认 50
    - **返回**: 会话列表（不含详情）
    """
    records = await sessions.list_for_user(session, user.id, limit)
    return [SessionOut.of(record) for record in records]


@router.get(
    "/{session_id}",
    summary="获取会话详情",
    description="获取指定会话的详细信息，包括图墙和当前素材。",
)
async def get_session(
    session_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> SessionDetailOut:
    """
    获取会话详情。

    - **session_id**: 会话 UUID
    - **返回**: 会话详细信息，包含：
      - 基本信息（ID、标题、创建/更新时间）
      - 当前素材
      - 图墙素材列表

    **可能错误**:
    - 404: 会话不存在
    """
    return await _detail(session, await _load(session, user, session_id))


@router.patch(
    "/{session_id}",
    summary="修改会话",
    description="更新会话标题或切换当前编辑的素材。",
)
async def patch_session(
    session_id: uuid.UUID,
    payload: SessionPatchIn,
    user: CurrentUser,
    session: SessionDep,
) -> SessionDetailOut:
    """
    修改会话。

    **路径参数**:
    - **session_id**: 会话 UUID

    **请求参数 (SessionPatchIn)**:
    - **title**: 新的会话标题（可选）
    - **current_asset_id**: 新的当前编辑素材 ID，用于切换当前正在编辑的图片（可选）

    **返回**: 更新后的会话详情（SessionDetailOut）

    **可能错误**:
    - 404: 会话或素材不存在
    """
    record = await _load(session, user, session_id)

    if payload.title is not None:
        record = await sessions.rename(session, record, payload.title)
    if payload.current_asset_id is not None:
        asset = await _asset(session, user, payload.current_asset_id)
        record = await sessions.switch_current(session, record, asset)

    return await _detail(session, record)


@router.get(
    "/{session_id}/history",
    summary="获取会话历史",
    description="获取指定会话的编辑历史记录。",
)
async def get_history(
    session_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> list[HistoryOut]:
    """
    获取会话的编辑历史。

    - **session_id**: 会话 UUID
    - **返回**: 编辑历史记录列表，按时间倒序

    **可能错误**:
    - 404: 会话不存在
    """
    record = await _load(session, user, session_id)
    entries = await sessions.history_of(session, record)
    return [HistoryOut.of(entry) for entry in entries]


@router.get(
    "/{session_id}/messages",
    summary="获取对话记录",
    description="获取会话内的自然语言修图指令对话，按时间正序返回。",
)
async def list_messages(
    session_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> list[TurnOut]:
    """
    获取会话的对话记录。

    - **session_id**: 会话 UUID
    - **返回**: 对话轮次列表（按创建时间正序）
    """
    record = await _load(session, user, session_id)
    return [TurnOut.of(turn) for turn in await agent_service.turns_of(session, record)]


@router.post(
    "/{session_id}/messages",
    status_code=status.HTTP_201_CREATED,
    summary="发送修图指令",
    description="用自然语言描述修图意图，由 AI 规划为工具调用并异步执行。",
)
async def send_message(
    session_id: uuid.UUID,
    payload: MessageIn,
    user: CurrentUser,
    session: SessionDep,
) -> TurnOut:
    """
    发送一条自然语言修图指令。

    **请求参数 (MessageIn)**:
    - **text**: 修图指令文本（必填，1-1000 字符）

    **返回**: 本轮对话（TurnOut），含规划结果与已投递的工具步骤

    - 指令会被规划模型解析为至多一个工具步骤，服务端校验后下发执行
    - 指令与修图无关时返回一句中文说明，不调用任何工具
    - 规划模型未配置时明确失败（status=failed），不会伪造成功结果
    """
    record = await _load(session, user, session_id)
    return TurnOut.of(await agent_service.respond(session, record, payload.text))