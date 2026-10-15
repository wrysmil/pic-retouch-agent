"""
后台用户管理服务。

所有方法都在事务内调用方手动 commit；审计记录与业务变更一并写入。
"""

import uuid
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AdminAuditLog, AuditAction, User, UserRole
from app.security import hash_password


class UsernameTaken(Exception):
    """用户名已被占用"""


class LastAdminViolation(Exception):
    """最后一个启用中的管理员不能被降级或停用。"""


class UserNotFound(Exception):
    """指定用户不存在。"""


async def list_users(
    session: AsyncSession,
    *,
    role: str | None = None,
    is_active: bool | None = None,
    keyword: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[User], int]:
    """按条件分页查询。返回 (本页用户, 总数)。"""
    filters = []
    if role:
        filters.append(User.role == UserRole(role))
    if is_active is not None:
        filters.append(User.is_active == is_active)
    if keyword:
        filters.append(User.username.ilike(f"{keyword}%"))

    where = and_(*filters) if filters else None
    count_stmt = select(func.count()).select_from(User)
    if where is not None:
        count_stmt = count_stmt.where(where)
    total = await session.scalar(count_stmt) or 0

    stmt = select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
    if where is not None:
        stmt = stmt.where(where)
    result = await session.scalars(stmt)
    return list(result), int(total)


async def create_user(
    session: AsyncSession,
    actor: User,
    *,
    username: str,
    password: str,
    role: Literal["user", "admin"] = "user",
    is_active: bool = True,
) -> User:
    """创建用户。管理员账号只能由后台或脚本创建，公开注册路径无权指定 role。"""
    now = datetime.now(UTC)
    user = User(
        username=username,
        password_hash=hash_password(password),
        role=UserRole(role),
        is_active=is_active,
        password_changed_at=now,
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise UsernameTaken from exc
    session.add(
        AdminAuditLog(
            actor_id=actor.id,
            action=AuditAction.USER_CREATED.value,
            target_kind="user",
            target_id=user.id,
            changes={"role": role, "is_active": is_active},
        )
    )
    return user


async def update_role(
    session: AsyncSession,
    actor: User,
    target_id: uuid.UUID,
    role: Literal["user", "admin"],
) -> User:
    """调整用户角色。降级最后一个启用管理员时拒绝。"""
    target = await session.get(User, target_id)
    if target is None:
        raise UserNotFound

    if target.role == UserRole(role):
        return target

    if target.role == UserRole.ADMIN and target.is_active and role == "user":
        await _ensure_other_admin(session, target.id)

    previous = target.role
    target.role = UserRole(role)
    session.add(
        AdminAuditLog(
            actor_id=actor.id,
            action=AuditAction.USER_ROLE_CHANGED.value,
            target_kind="user",
            target_id=target.id,
            changes={"from": previous.value, "to": role},
        )
    )
    return target


async def set_active(
    session: AsyncSession,
    actor: User,
    target_id: uuid.UUID,
    is_active: bool,
) -> User:
    """启用或停用账号。停用最后一个启用管理员时拒绝。"""
    target = await session.get(User, target_id)
    if target is None:
        raise UserNotFound

    if target.is_active == is_active:
        return target

    if target.role == UserRole.ADMIN and target.is_active and not is_active:
        await _ensure_other_admin(session, target.id)

    target.is_active = is_active
    # 禁用/启用都撤销全部现存会话，避免旧令牌继续持有有效权限
    target.auth_version = target.auth_version + 1
    session.add(
        AdminAuditLog(
            actor_id=actor.id,
            action=(
                AuditAction.USER_ENABLED.value
                if is_active
                else AuditAction.USER_DISABLED.value
            ),
            target_kind="user",
            target_id=target.id,
            changes={"is_active": is_active},
        )
    )
    return target


async def reset_password(
    session: AsyncSession,
    actor: User,
    target_id: uuid.UUID,
    new_password: str,
) -> User:
    """重置密码并自增 auth_version，旧会话立即失效。"""
    target = await session.get(User, target_id)
    if target is None:
        raise UserNotFound

    now = datetime.now(UTC)
    target.password_hash = hash_password(new_password)
    target.password_changed_at = now
    target.auth_version = target.auth_version + 1
    session.add(
        AdminAuditLog(
            actor_id=actor.id,
            action=AuditAction.USER_PASSWORD_RESET.value,
            target_kind="user",
            target_id=target.id,
            changes={},  # 不写新密码
        )
    )
    return target


async def revoke_sessions(
    session: AsyncSession,
    actor: User,
    target_id: uuid.UUID,
) -> User:
    """撤销目标用户全部现存会话。仅递增 auth_version。"""
    target = await session.get(User, target_id)
    if target is None:
        raise UserNotFound

    target.auth_version = target.auth_version + 1
    session.add(
        AdminAuditLog(
            actor_id=actor.id,
            action=AuditAction.USER_SESSIONS_REVOKED.value,
            target_kind="user",
            target_id=target.id,
            changes={"auth_version": target.auth_version},
        )
    )
    return target


async def _ensure_other_admin(session: AsyncSession, exclude_id: uuid.UUID) -> None:
    """除自己外是否仍有至少一个启用中的管理员。没有则拒绝操作。"""
    stmt = select(func.count()).select_from(User).where(
        User.role == UserRole.ADMIN,
        User.is_active.is_(True),
        User.id != exclude_id,
    )
    other = await session.scalar(stmt) or 0
    if other < 1:
        raise LastAdminViolation("必须保留至少一个启用的管理员")