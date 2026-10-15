"""后台审计写入。

被服务层/路由层调用，与业务事务同一会话提交，确保审计不丢。
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AdminAuditLog, AuditAction


async def log(
    session: AsyncSession,
    actor_id: uuid.UUID,
    action: AuditAction,
    target_id: uuid.UUID,
    changes: dict | None = None,
    target_kind: str = "user",
) -> AdminAuditLog:
    """追加一条审计记录。调用方负责 commit；此处只 add。"""
    entry = AdminAuditLog(
        actor_id=actor_id,
        action=action.value,
        target_kind=target_kind,
        target_id=target_id,
        changes=changes or {},
    )
    session.add(entry)
    return entry