from arq.connections import RedisSettings

from app.config import get_settings
from app.tasks import TASKS

settings = get_settings()


class WorkerSettings:
    """ARQ worker 入口。新增异步任务需在 app.tasks.TASKS 中注册。"""

    # worker 连接的 Redis 地址，从这里拉取待执行的任务
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    # 该 worker 可执行的任务函数清单（来自 app/tasks/ 目录）
    functions = TASKS
    # 单个 worker 进程最多同时并发执行的任务数
    max_jobs = 4
    # 单个任务最长执行时间（秒），超时会被终止
    job_timeout = 300
    # 任务执行结果在 Redis 中的保留时长（秒），过期自动清理
    keep_result = 3600
