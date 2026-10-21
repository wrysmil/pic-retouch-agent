import uuid
from datetime import UTC, datetime

from arq import cron

from app.db import SessionFactory
from app.queue import enqueue, enqueue_job
from app.services import agent as agent_service
from app.services import recovery


async def recovery_tick(_: dict) -> None:
    """周期扫描孤立任务。并发实例靠数据库租约/条件更新抢占。"""

    async with SessionFactory() as session:
        await recovery.recover(
            session,
            enqueue_planning=lambda turn_id: enqueue_job(
                "plan_turn",
                f"recover-plan:{turn_id}:{int(datetime.now(UTC).timestamp() // 60)}",
                turn_id,
            ),
            enqueue_tool=lambda run_id: enqueue("run_tool", uuid.UUID(str(run_id))),
            resume_execution=lambda turn_id: agent_service.resume_execution(
                session, turn_id
            ),
        )


RECOVERY_CRON = cron(
    recovery_tick,
    second={0, 30},
    run_at_startup=True,
    unique=True,
    name="recovery_tick",
)
