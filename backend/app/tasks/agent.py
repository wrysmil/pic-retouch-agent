import uuid

from app.db import SessionFactory
from app.services import agent as agent_service


async def plan_turn(_: dict, turn_id: uuid.UUID) -> None:
    """后台规划一轮对话。run id 复用 turn id，ARQ 重投不会并行规划同一轮。"""
    async with SessionFactory() as session:
        await agent_service.plan_turn(session, turn_id)
