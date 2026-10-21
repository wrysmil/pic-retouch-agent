"""
任务执行服务层。

提供任务记录的创建、查询、状态更新和事件发布功能。
任务状态变更时会同步发布到 Redis，供 SSE 推送。
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import events
from app.models.tool_run import RunStatus, ToolRun


class RunNotFound(Exception):
    """任务不存在或无权访问"""

    pass


def snapshot(run: ToolRun) -> dict:
    """
    生成任务的快照字典，用于 SSE 推送和状态序列化。

    - **run**: 任务记录
    - **返回**: 包含 id、tool、status、progress、stage、error 的字典
    """
    return {
        "id": str(run.id),
        "tool": run.tool,
        "status": run.status,
        "progress": run.progress,
        "stage": run.stage,
        "error": run.error,
        "result": run.result or {},
        "runtime_config_version_id": str(run.runtime_config_version_id) if run.runtime_config_version_id else None,
    }


async def create(
    session: AsyncSession,
    user_id: uuid.UUID,
    tool: str,
    params: dict,
    session_id: uuid.UUID | None = None,
    *,
    runtime_config_version_id: uuid.UUID | None = None,
    turn_id: uuid.UUID | None = None,
    step_id: str | None = None,
    attempt: int = 1,
    commit: bool = True,
) -> ToolRun:
    """
    创建新任务记录。

    - **runtime_config_version_id**: 任务调度时锁定的模型版本；留空表示老任务未启用版本机制
    - **commit**: 为 False 时只 flush 分配 id，由调用方把任务与额度预占放在同一事务提交
    """
    run = ToolRun(
        user_id=user_id,
        session_id=session_id,
        tool=tool,
        params=params,
        stage="等待开始",
        runtime_config_version_id=runtime_config_version_id,
        turn_id=turn_id,
        step_id=step_id,
        attempt=attempt,
    )
    session.add(run)
    await session.flush()
    if commit:
        await session.commit()
        await session.refresh(run)
    return run


async def get(session: AsyncSession, run_id: uuid.UUID, user_id: uuid.UUID) -> ToolRun:
    """按 ID 获取任务，并校验归属。"""
    run = await session.scalar(
        select(ToolRun).where(ToolRun.id == run_id, ToolRun.user_id == user_id)
    )
    if run is None:
        raise RunNotFound
    return run


async def load(session: AsyncSession, run_id: uuid.UUID) -> ToolRun:
    """按 ID 加载任务（不校验归属，用于 Worker）。"""
    run = await session.get(ToolRun, run_id)
    if run is None:
        raise RunNotFound
    return run


async def _commit(session: AsyncSession, run: ToolRun) -> None:
    """提交变更并发布事件。"""
    await session.commit()
    await events.publish(run.id, snapshot(run))


async def start(session: AsyncSession, run: ToolRun) -> None:
    """标记任务开始执行。"""
    run.status = RunStatus.RUNNING
    run.started_at = datetime.now(UTC)
    run.progress = 5
    run.stage = "已开始"
    await _commit(session, run)


async def report(
    session: AsyncSession,
    run: ToolRun,
    progress: int,
    stage: str,
    result: dict | None = None,
) -> None:
    """报告任务进度。"""
    run.progress = max(run.progress, progress)
    run.stage = stage
    if result is not None:
        run.result = result
    await _commit(session, run)


async def finish(
    session: AsyncSession,
    run: ToolRun,
    *,
    status: RunStatus,
    result: dict | None = None,
    error: str | None = None,
) -> None:
    """标记任务结束。"""
    run.status = status
    run.result = result or {}
    run.error = error
    run.progress = 100 if status is RunStatus.SUCCEEDED else run.progress
    run.stage = "已完成" if status is RunStatus.SUCCEEDED else "已结束"
    run.finished_at = datetime.now(UTC)
    await _commit(session, run)