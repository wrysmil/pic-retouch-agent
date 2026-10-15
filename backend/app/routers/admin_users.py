"""后台用户管理接口。

所有写操作要求管理员身份（AdminUser 依赖）。
"""

import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError

from app.db import SessionDep
from app.deps import AdminUser
from app.models import User
from app.schemas.admin_users import (
    AdminActiveUpdate,
    AdminCreateUser,
    AdminResetPassword,
    AdminRoleUpdate,
    AdminUserList,
    AdminUserOut,
)
from app.services import admin_users as admin_users_service

router = APIRouter(prefix="/admin/users", tags=["admin:users"])


def _serialize(user: User) -> AdminUserOut:
    return AdminUserOut(
        id=user.id,
        username=user.username,
        role=user.role.value,
        is_active=user.is_active,
        auth_version=user.auth_version,
        last_login_at=user.last_login_at.isoformat() if user.last_login_at else None,
        created_at=user.created_at.isoformat(),
        password_changed_at=user.password_changed_at.isoformat()
        if user.password_changed_at
        else None,
    )


def _parse_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "无效的用户 ID") from exc


@router.get(
    "",
    response_model=AdminUserList,
    summary="用户列表",
)
async def list_users(
    _actor: AdminUser,
    session: SessionDep,
    role: str | None = Query(default=None, pattern="^(user|admin)$"),
    is_active: bool | None = None,
    keyword: str | None = Query(default=None, max_length=32),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> AdminUserList:
    items, total = await admin_users_service.list_users(
        session,
        role=role,
        is_active=is_active,
        keyword=keyword,
        limit=limit,
        offset=offset,
    )
    return AdminUserList(
        total=total,
        items=[_serialize(user) for user in items],
    )


@router.post(
    "",
    response_model=AdminUserOut,
    status_code=status.HTTP_201_CREATED,
    summary="创建用户",
)
async def create_user(
    body: AdminCreateUser,
    actor: AdminUser,
    session: SessionDep,
) -> AdminUserOut:
    try:
        user = await admin_users_service.create_user(
            session,
            actor,
            username=body.username,
            password=body.password,
            role=body.role,
            is_active=body.is_active,
        )
    except admin_users_service.UsernameTaken:
        raise HTTPException(status.HTTP_409_CONFLICT, "该用户名已被占用") from None
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "用户创建冲突") from None
    await session.commit()
    await session.refresh(user)
    return _serialize(user)


@router.get(
    "/{user_id}",
    response_model=AdminUserOut,
    summary="用户详情",
)
async def get_user(user_id: str, _actor: AdminUser, session: SessionDep) -> AdminUserOut:
    user = await session.get(User, _parse_uuid(user_id))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")
    return _serialize(user)


@router.patch(
    "/{user_id}/role",
    response_model=AdminUserOut,
    summary="调整用户角色",
)
async def update_role(
    user_id: str,
    body: AdminRoleUpdate,
    actor: AdminUser,
    session: SessionDep,
) -> AdminUserOut:
    try:
        user = await admin_users_service.update_role(session, actor, _parse_uuid(user_id), body.role)
    except admin_users_service.UserNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在") from None
    except admin_users_service.LastAdminViolation as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    await session.commit()
    await session.refresh(user)
    return _serialize(user)


@router.patch(
    "/{user_id}/active",
    response_model=AdminUserOut,
    summary="启用或停用账号",
)
async def update_active(
    user_id: str,
    body: AdminActiveUpdate,
    actor: AdminUser,
    session: SessionDep,
) -> AdminUserOut:
    try:
        user = await admin_users_service.set_active(session, actor, _parse_uuid(user_id), body.is_active)
    except admin_users_service.UserNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在") from None
    except admin_users_service.LastAdminViolation as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    await session.commit()
    await session.refresh(user)
    return _serialize(user)


@router.post(
    "/{user_id}/reset-password",
    response_model=AdminUserOut,
    summary="重置密码并撤销会话",
)
async def reset_password(
    user_id: str,
    body: AdminResetPassword,
    actor: AdminUser,
    session: SessionDep,
) -> AdminUserOut:
    try:
        user = await admin_users_service.reset_password(
            session, actor, _parse_uuid(user_id), body.new_password
        )
    except admin_users_service.UserNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在") from None
    await session.commit()
    await session.refresh(user)
    return _serialize(user)


@router.post(
    "/{user_id}/revoke-sessions",
    response_model=AdminUserOut,
    summary="撤销全部会话",
)
async def revoke_sessions(
    user_id: str,
    actor: AdminUser,
    session: SessionDep,
) -> AdminUserOut:
    try:
        user = await admin_users_service.revoke_sessions(session, actor, _parse_uuid(user_id))
    except admin_users_service.UserNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在") from None
    await session.commit()
    await session.refresh(user)
    return _serialize(user)