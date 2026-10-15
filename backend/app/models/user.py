import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TIMESTAMPTZ, UUIDBase, enum_column


class UserRole(enum.StrEnum):
    """用户角色。普通用户用 USER，管理员用 ADMIN。注册路径只能产出 USER。"""

    USER = "user"
    ADMIN = "admin"


class User(UUIDBase):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    role: Mapped[UserRole] = mapped_column(
        enum_column(UserRole), default=UserRole.USER, nullable=False
    )
    # 禁用后拒绝登录和业务请求，但保留历史任务与统计归属
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # 递增即可作废旧 JWT。重置密码或管理员撤销会话都会自增
    auth_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, default=None)
    password_changed_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, default=None)


# 暴露给 schema 层复用，避免分散定义
__all__ = ["User", "UserRole"]