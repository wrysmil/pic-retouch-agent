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
    }


async def create(session: AsyncSession, user_id: uuid.UUID, tool: str, params: dict) -> ToolRun:
    """
    创建新任务记录。

    - **session**: 数据库会话
    - **user_id**: 任务归属的用户 ID
    - **tool**: 工具标识（如 "generate_image"）
    - **params**: 任务参数字典
    - **返回**: 创建的任务记录
    """
    run = ToolRun(user_id=user_id, tool=tool, params=params, stage="等待开始")
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


async def get(session: AsyncSession, run_id: uuid.UUID, user_id: uuid.UUID) -> ToolRun:
    """
    按 ID 获取任务，并校验归属。

    - **session**: 数据库会话
    - **run_id**: 任务 ID
    - **user_id**: 用户 ID（用于归属校验）
    - **返回**: 任务记录
    - **抛出**: RunNotFound 不存在或无权访问
    """
    run = await session.scalar(
        select(ToolRun).where(ToolRun.id == run_id, ToolRun.user_id == user_id)
    )
    if run is None:
        raise RunNotFound
    return run


async def load(session: AsyncSession, run_id: uuid.UUID) -> ToolRun:
    """
    按 ID 加载任务（不校验归属，用于 Worker）。

    - **session**: 数据库会话
    - **run_id**: 任务 ID
    - **返回**: 任务记录
    - **抛出**: RunNotFound 不存在
    """
    run = await session.get(ToolRun, run_id)
    if run is None:
        raise RunNotFound
    return run


async def _commit(session: AsyncSession, run: ToolRun) -> None:
    """
    内部方法：提交变更并发布事件。

    - **session**: 数据库会话
    - **run**: 任务记录
    """
    await session.commit()
    await events.publish(run.id, snapshot(run))


async def start(session: AsyncSession, run: ToolRun) -> None:
    """
    标记任务开始执行。

    - **session**: 数据库会话
    - **run**: 任务记录
    - **效果**: 设置 status=RUNNING, progress=5, stage="已开始"
    """
    run.status = RunStatus.RUNNING
    run.started_at = datetime.now(UTC)
    run.progress = 5
    run.stage = "已开始"
    await _commit(session, run)


async def report(session: AsyncSession, run: ToolRun, progress: int, stage: str) -> None:
    """
    报告任务进度。

    - **session**: 数据库会话
    - **run**: 任务记录
    - **progress**: 进度百分比（0-100）
    - **stage**: 当前阶段描述（如 "正在生成"、"保存候选图"）
    - **效果**: 更新进度和阶段描述，发布事件
    """
    run.progress = max(run.progress, progress)
    run.stage = stage
    await _commit(session, run)


async def finish(
    session: AsyncSession,
    run: ToolRun,
    *,
    status: RunStatus,
    result: dict | None = None,
    error: str | None = None,
) -> None:
    """
    标记任务结束。

    - **session**: 数据库会话
    - **run**: 任务记录
    - **status**: 最终状态（SUCCEEDED 或 FAILED）
    - **result**: 成功时的结果数据（如 asset_ids 列表）
    - **error**: 失败时的错误信息
    - **效果**: 设置状态、结果/错误、进度为 100（成功时）、发布事件
    """
    run.status = status
    run.result = result or {}
    run.error = error
    run.progress = 100 if status is RunStatus.SUCCEEDED else run.progress
    run.stage = "已完成" if status is RunStatus.SUCCEEDED else "已结束"
    run.finished_at = datetime.now(UTC)
    await _commit(session, run)