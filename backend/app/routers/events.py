"""
SSE 事件推送相关接口。

提供任务执行状态的实时推送功能，通过 Server-Sent Events (SSE) 协议实现。
"""

import asyncio
import json
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Header, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse

from app import events
from app.db import SessionDep
from app.deps import CurrentUser
from app.models import AgentRun
from app.models.tool_run import RunStatus
from app.services import runs, sessions, turn_events
from app.services.runs import RunNotFound
from app.services.sessions import SessionNotFound

router = APIRouter(prefix="/events", tags=["events"])

_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}

# 超时后主动断开，客户端重连时会先收到快照，不会丢状态
_MAX_STREAM_SECONDS = 600.0


def _frame(payload: dict) -> str:
    """将字典 payload 序列化为 SSE data 帧。"""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _event_frame(payload: dict) -> str:
    """轮次事件带 id，浏览器重连时可用 Last-Event-ID 继续。"""
    return f"id: {payload.get('seq', 0)}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _envelope(turn: AgentRun, type_: str, payload: dict) -> dict:
    return {
        "event_id": None,
        "seq": turn.last_event_seq,
        "turn_id": str(turn.id),
        "planning_attempt": turn.planning_attempt,
        "type": type_,
        "payload": payload,
    }


@router.get(
    "/runs/{run_id}",
    summary="订阅任务进度",
    description="通过 SSE 实时推送任务执行状态，支持进度更新和完成/失败通知。",
    response_class=StreamingResponse,
)
async def stream_run(
    run_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> Response:
    """
    订阅任务执行进度的 SSE 流。

    - **run_id**: 任务 UUID
    - **返回**: text/event-stream 类型的数据流

    **SSE 事件格式**:
    ```json
    {
        "status": "pending|running|completed|failed",
        "progress": 50,
        "message": "正在生成图片...",
        "result": {...}
    }
    ```

    **事件流程**:
    1. 首先发送当前状态的快照
    2. 如果任务已结束，立即断开
    3. 否则保持连接，实时推送进度更新
    4. 任务完成后发送最终状态，然后断开

    **可能错误**:
    - 404: 任务不存在
    """
    try:
        await runs.get(session, run_id, user.id)
    except RunNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务不存在") from exc

    async def stream() -> AsyncIterator[str]:
        """
        SSE 流生成器：将 Redis 消息实时转发给前端。

        数据流：
        ┌─────────┐    publish    ┌─────────┐    get_message    ┌─────────┐    yield    ┌─────────┐
        │ Worker  │ ───────────→  │  Redis  │ ───────────────→  │  SSE端点 │ ─────────→  │  浏览器  │
        │ (发布者) │               │ (通道)  │                  │ (转发器) │             │ (前端)  │
        └─────────┘               └─────────┘                  └─────────┘             └─────────┘
        """
        # 先订阅再读快照，否则任务在两步之间结束会让连接一直空等
        # 解释：如果先读快照再订阅，快照和订阅之间任务完成的消息会丢失
        #       先订阅保证：任何时刻的进度变化都能被捕获
        async with events.subscribe(run_id) as messages:
            # 发送当前状态快照（前端的"第一帧"）
            run = await runs.get(session, run_id, user.id)
            yield _frame(runs.snapshot(run))

            # 如果任务已经结束（快照就是终态），直接断开连接
            # 不用继续监听 Redis，因为不会再有新消息了
            if run.status.is_terminal:
                return

            # 设置最大连接时长（10分钟），防止资源泄漏
            deadline = asyncio.get_running_loop().time() + _MAX_STREAM_SECONDS

            # 循环监听 Redis Pub/Sub 消息
            async for payload in messages:
                # payload 为空 = Redis 15秒内无消息（超时）
                # 这不是错误，是正常的空闲状态
                if payload is None:
                    # 检查是否达到最大连接时长
                    if asyncio.get_running_loop().time() > deadline:
                        return  # 超时断开，让客户端重连
                    # 没超时则发送 ping 保持连接（HTTP keep-alive）
                    yield ": ping\n\n"
                    continue

                # 有实际的进度更新，转发给前端
                yield _frame(payload)

                # 检查是否是终态（completed/failed），是则断开
                # 不需要再监听了，任务已经结束
                if RunStatus(payload["status"]).is_terminal:
                    return

    return StreamingResponse(stream(), media_type="text/event-stream", headers=_HEADERS)


@router.get(
    "/agent-runs/{turn_id}",
    summary="订阅轮次规划与执行事件",
    description="先发轮次快照，再推送规划草稿、正式计划与步骤状态；断开不影响后台任务。",
    response_class=StreamingResponse,
)
async def stream_turn(
    turn_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    after_seq: int = Query(default=0, ge=0),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
) -> Response:
    turn = await session.get(AgentRun, turn_id)
    if turn is None or turn.session_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "对话不存在")
    try:
        await sessions.get_for_user(session, turn.session_id, user.id)
    except SessionNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "对话不存在") from exc

    cursor = after_seq
    if last_event_id and last_event_id.isdigit():
        cursor = max(cursor, int(last_event_id))

    # 流会持续数分钟，先释放请求级事务，避免一直占用数据库连接
    await session.rollback()

    async def stream() -> AsyncIterator[str]:
        # 先订阅再读快照：两步之间的新事件会进入队列，按 seq 去重后补发
        async with events.subscribe_turn(turn_id) as messages:
            from app.db import SessionFactory

            async with SessionFactory() as snap_session:
                current = await snap_session.get(AgentRun, turn_id)
                if current is None:
                    return
                snapshot = await turn_events.snapshot(current)
            yield _event_frame(
                _envelope(current, "turn.snapshot", {"turn": snapshot, "after_seq": cursor})
            )
            last_sent = current.last_event_seq
            if snapshot["phase"] in {"completed", "failed", "canceled"}:
                return

            deadline = asyncio.get_running_loop().time() + _MAX_STREAM_SECONDS
            async for message in messages:
                if message is None:
                    if asyncio.get_running_loop().time() > deadline:
                        return
                    yield ": ping\n\n"
                    continue

                seq = int(message.get("seq") or 0)
                if seq <= last_sent:
                    continue
                last_sent = seq
                yield _event_frame(message)

                type_ = message.get("type")
                phase = ((message.get("payload") or {}).get("turn") or {}).get("phase")
                if type_ == "planning.failed" or phase in {
                    "completed",
                    "failed",
                    "canceled",
                }:
                    return

    return StreamingResponse(stream(), media_type="text/event-stream", headers=_HEADERS)