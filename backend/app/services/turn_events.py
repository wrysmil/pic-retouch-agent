"""轮次事件的持久化与唤醒。

事件先落 agent_events，再通过 Redis 通知 SSE；Redis 丢消息不影响恢复。
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import events
from app.models import AgentEvent, AgentRun
from app.schemas.agent import TurnOut


async def append(
    session: AsyncSession,
    turn: AgentRun,
    type_: str,
    payload: dict | None = None,
) -> AgentEvent:
    """在轮次内追加事件。seq 由行上的 last_event_seq 条件自增，天然串行。"""

    seq = await session.scalar(
        update(AgentRun)
        .where(AgentRun.id == turn.id)
        .values(last_event_seq=AgentRun.last_event_seq + 1)
        .returning(AgentRun.last_event_seq)
    )
    turn.last_event_seq = int(seq or 0)
    event = AgentEvent(
        turn_id=turn.id,
        seq=int(seq or 0),
        type=type_,
        payload=payload or {},
    )
    session.add(event)
    await session.flush()
    return event


def envelope(turn: AgentRun, event: AgentEvent) -> dict:
    return {
        "event_id": str(event.id),
        "seq": event.seq,
        "turn_id": str(turn.id),
        "planning_attempt": turn.planning_attempt,
        "type": event.type,
        "timestamp": datetime.now(UTC).isoformat(),
        "payload": event.payload or {},
    }


async def emit(
    session: AsyncSession,
    turn: AgentRun,
    type_: str,
    payload: dict | None = None,
) -> dict:
    """追加事件并立即提交、唤醒 SSE。用于规划阶段的渐进事件。"""

    event = await append(session, turn, type_, payload)
    message = envelope(turn, event)
    await session.commit()
    await events.publish_turn(turn.id, message)
    return message


async def commit_and_publish(
    session: AsyncSession,
    turn: AgentRun,
    type_: str,
    payload: dict | None = None,
) -> dict:
    """把当前事务里的业务状态与事件一起提交，再唤醒 SSE。"""

    event = await append(session, turn, type_, payload)
    message = envelope(turn, event)
    await session.commit()
    await events.publish_turn(turn.id, message)
    return message


async def snapshot(turn: AgentRun) -> dict:
    return TurnOut.of(turn).model_dump(mode="json")


async def list_after(
    session: AsyncSession, turn_id: uuid.UUID, after_seq: int = 0
) -> list[AgentEvent]:
    return list(
        await session.scalars(
            select(AgentEvent)
            .where(AgentEvent.turn_id == turn_id, AgentEvent.seq > after_seq)
            .order_by(AgentEvent.seq)
        )
    )
