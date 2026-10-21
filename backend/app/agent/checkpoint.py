"""规划图的 Postgres checkpoint 生命周期。

checkpoint 只保存可序列化的图状态（目标、上下文、计划），不保存模型客户端、
数据库连接或密钥。初始化失败时规划仍可运行，只是不写 checkpoint。
"""

import logging
from contextlib import AbstractAsyncContextManager

from app.config import get_settings

logger = logging.getLogger(__name__)

_cm: AbstractAsyncContextManager | None = None
_saver = None


def _dsn() -> str:
    """psycopg 不认 SQLAlchemy 的 +asyncpg 驱动前缀。"""
    url = get_settings().database_url
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


def saver():
    return _saver


async def init_saver():
    """worker 启动时调用一次。setup 只在无表时建表，不放在每次请求里。"""

    global _cm, _saver
    if _saver is not None:
        return _saver
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        _cm = AsyncPostgresSaver.from_conn_string(_dsn())
        _saver = await _cm.__aenter__()
        await _saver.setup()
        logger.info("规划图 checkpoint 已启用")
    except Exception:
        logger.exception("规划图 checkpoint 初始化失败，将跳过持久化")
        _saver = None
        if _cm is not None:
            try:
                await _cm.__aexit__(None, None, None)
            except Exception:
                pass
            _cm = None
    return _saver


async def close_saver() -> None:
    global _cm, _saver
    if _cm is not None:
        await _cm.__aexit__(None, None, None)
    _cm = None
    _saver = None
