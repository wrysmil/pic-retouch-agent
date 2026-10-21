import uuid

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.config import get_settings

_pool: ArqRedis | None = None


async def queue() -> ArqRedis:
    global _pool
    if _pool is None:
        _pool = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
    return _pool


async def close_queue() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None


async def enqueue(task: str, run_id: uuid.UUID) -> None:
    """以 run id 作为任务 ID，重复投递同一 run 不会产生第二次执行。"""
    await enqueue_job(task, str(run_id), run_id)


async def enqueue_job(task: str, job_id: str, *args) -> None:
    """显式指定 job id。恢复扫描用它避开已经卡住的旧 job，业务侧仍靠租约/状态去重。"""
    pool = await queue()
    await pool.enqueue_job(task, *args, _job_id=job_id)