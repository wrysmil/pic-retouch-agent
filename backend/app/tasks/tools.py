import uuid

from app.db import SessionFactory
from app.models.tool_run import RunStatus
from app.services import runs, tools


async def run_tool(_: dict, run_id: uuid.UUID) -> None:
    """通用工具执行任务。run id 同时作为队列任务 ID，重复投递不会重复执行。"""
    async with SessionFactory() as session:
        try:
            run = await runs.load(session, run_id)
        except runs.RunNotFound:
            return
        # 只有排队中的任务才可领取；RUNNING 说明已有 worker 在执行或崩溃后状态未知
        if run.status is not RunStatus.QUEUED:
            return

        await tools.execute(session, run)