"""
健康检查相关接口。

用于探测服务状态，包括 API、数据库和对象存储的可用性。
"""

import asyncio
from collections.abc import Awaitable

from fastapi import APIRouter
from sqlalchemy import text

from app import storage
from app.db import SessionDep

router = APIRouter(prefix="/health", tags=["health"])


async def _probe(awaitable: Awaitable) -> str:
    """探测服务是否可用，返回 'ok' 或错误信息。"""
    try:
        await awaitable
        return "ok"
    except Exception as exc:  # noqa: BLE001 - 健康检查需要报告任意故障原因
        return f"error: {type(exc).__name__}"


@router.get(
    "",
    summary="健康检查",
    description="检查 API、数据库和对象存储的连接状态。",
)
async def health(session: SessionDep) -> dict[str, str]:
    """
    健康检查接口。

    同时检查以下服务的可用性：
    - **api**: API 服务本身，始终返回 "ok"
    - **database**: 数据库连接状态
    - **storage**: 对象存储（OSS/S3）连接状态

    - **返回**: 各服务状态字典

    **返回值示例**:
    ```json
    {
        "api": "ok",
        "database": "ok",
        "storage": "ok"
    }
    ```
    """
    database, object_storage = await asyncio.gather(
        _probe(session.execute(text("select 1"))),
        _probe(asyncio.to_thread(storage.ensure_bucket)),
    )
    return {"api": "ok", "database": database, "storage": object_storage}