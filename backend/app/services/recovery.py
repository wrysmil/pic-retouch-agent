"""轻量恢复扫描：只处理能安全重投的孤立任务。

- 规划租约过期的 planning 轮次：重新投递同一 turn。
- 已建记录但迟迟未开始的 queued ToolRun：用原 run_id 重投（ARQ job id 去重）。

结果未知的外部调用、RUNNING 中崩溃的步骤不在本轮自动重跑，留给人工核查。
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import AgentEvent, AgentPhase, AgentRun, ToolRun
from app.models.tool_run import RunStatus

logger = logging.getLogger(__name__)


async def claim_stale_planning(session: AsyncSession, limit: int = 20) -> list[uuid.UUID]:
    """用条件更新抢占过期租约，避免多个 worker 同时恢复同一轮。"""

    now = datetime.now(UTC)
    lease = timedelta(seconds=max(30, get_settings().agent_plan_lease_seconds))
    candidates = (
        select(AgentRun.id)
        .where(
            AgentRun.phase == AgentPhase.PLANNING,
            AgentRun.created_at < now - timedelta(seconds=30),
            or_(
                AgentRun.planning_lease_until.is_(None),
                AgentRun.planning_lease_until < now,
            ),
        )
        .order_by(AgentRun.created_at)
        .limit(limit)
        .scalar_subquery()
    )
    # 外层的条件在拿到行锁后会重新判断，并发实例只有一个能领取成功
    claimed = await session.execute(
        update(AgentRun)
        .where(
            AgentRun.id.in_(candidates),
            AgentRun.phase == AgentPhase.PLANNING,
            or_(
                AgentRun.planning_lease_until.is_(None),
                AgentRun.planning_lease_until < now,
            ),
        )
        .values(planning_lease_until=now + lease)
        .returning(AgentRun.id)
    )
    ids = [row[0] for row in claimed]
    await session.commit()
    return ids


async def stale_queued_runs(
    session: AsyncSession, limit: int = 50
) -> list[uuid.UUID]:
    now = datetime.now(UTC)
    return list(
        await session.scalars(
            select(ToolRun.id)
            .where(
                ToolRun.status == RunStatus.QUEUED,
                ToolRun.created_at < now - timedelta(seconds=60),
            )
            .order_by(ToolRun.created_at)
            .limit(limit)
        )
    )


async def stale_executing_turns(
    session: AsyncSession, limit: int = 20
) -> list[uuid.UUID]:
    """executing 阶段但长时间没有新事件的轮次：worker 崩了就卡在这里。"""

    now = datetime.now(UTC)
    recent = (
        select(AgentEvent.turn_id)
        .where(AgentEvent.created_at > now - timedelta(seconds=60))
        .scalar_subquery()
    )
    return list(
        await session.scalars(
            select(AgentRun.id)
            .where(
                AgentRun.phase == AgentPhase.EXECUTING,
                AgentRun.created_at < now - timedelta(seconds=60),
                AgentRun.id.notin_(recent),
            )
            .order_by(AgentRun.created_at)
            .limit(limit)
        )
    )


async def recover(
    session: AsyncSession, *, enqueue_planning, enqueue_tool, resume_execution=None
) -> tuple[int, int]:
    turns = await claim_stale_planning(session)
    for turn_id in turns:
        try:
            await enqueue_planning(turn_id)
        except Exception:  # pragma: no cover - 队列不可用时下一轮再试
            logger.exception("恢复规划投递失败 turn_id=%s", turn_id)

    runs = await stale_queued_runs(session)
    for run_id in runs:
        try:
            await enqueue_tool(run_id)
        except Exception:  # pragma: no cover
            logger.exception("恢复工具投递失败 run_id=%s", run_id)

    resumed = 0
    if resume_execution is not None:
        for turn_id in await stale_executing_turns(session):
            try:
                await resume_execution(turn_id)
                resumed += 1
            except Exception:  # pragma: no cover
                logger.exception("恢复执行推进失败 turn_id=%s", turn_id)

    if turns or runs or resumed:
        logger.info(
            "恢复扫描：planning=%s queued_runs=%s resumed=%s", len(turns), len(runs), resumed
        )
    return len(turns), len(runs)
