import asyncio
import sys

from arq.connections import RedisSettings

# psycopg 的异步连接不支持 Windows 默认的 ProactorEventLoop；
# 必须在 ARQ 创建事件循环之前切换，否则 checkpoint saver 无法初始化。
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.agent.checkpoint import close_saver, init_saver
from app.config import get_settings
from app.tasks import CRONS, TASKS

settings = get_settings()


async def on_startup(_: dict) -> None:
    # checkpoint 建表只在这里做一次；失败时规划仍可用，只是不持久化图状态
    await init_saver()


async def on_shutdown(_: dict) -> None:
    await close_saver()


class WorkerSettings:
    """ARQ worker 入口。新增异步任务需在 app.tasks.TASKS 中注册。"""

    # worker 连接的 Redis 地址，从这里拉取待执行的任务
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    # 该 worker 可执行的任务函数清单（来自 app/tasks/ 目录）
    functions = TASKS
    cron_jobs = CRONS
    on_startup = on_startup
    on_shutdown = on_shutdown
    # 单个 worker 进程最多同时并发执行的任务数
    max_jobs = 4
    # 单个任务最长执行时间（秒），超时会被终止
    job_timeout = 300
    # 任务执行结果在 Redis 中的保留时长（秒），过期自动清理
    keep_result = 3600
