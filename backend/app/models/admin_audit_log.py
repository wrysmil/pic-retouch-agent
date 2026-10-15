import enum
import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import UUIDBase


class AuditAction(enum.StrEnum):
    """后台写操作的动作枚举。后续阶段新增配置/用量相关动作时再扩展。"""

    USER_CREATED = "user.created"
    USER_ROLE_CHANGED = "user.role_changed"
    USER_ENABLED = "user.enabled"
    USER_DISABLED = "user.disabled"
    USER_PASSWORD_RESET = "user.password_reset"
    USER_SESSIONS_REVOKED = "user.sessions_revoked"


class AdminAuditLog(UUIDBase):
    """后台管理写操作审计。一条记录覆盖一次写入，操作者与对象在同一行确认。"""

    __tablename__ = "admin_audit_logs"

    actor_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    action: Mapped[str] = mapped_column(String(48))
    # 对象表名 + 对象 id，用字符串而非外键是为了不绑定生命周期
    target_kind: Mapped[str] = mapped_column(String(32))
    target_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), index=True)
    # 脱敏后的变更摘要，比如角色变更前后值；不允许写入密码/密钥/完整请求体
    changes: Mapped[dict] = mapped_column(JSONB, default=dict)