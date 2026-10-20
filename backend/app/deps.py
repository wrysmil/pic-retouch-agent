from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status

from app.db import SessionDep
from app.models import User
from app.security import ADMIN_SESSION_COOKIE, SESSION_COOKIE, read_token
from app.services import auth as auth_service

_UNAUTHENTICATED = HTTPException(status.HTTP_401_UNAUTHORIZED, "未登录或会话已过期")
_FORBIDDEN = HTTPException(status.HTTP_403_FORBIDDEN, "需要管理员权限")


async def _user_from_token(session: SessionDep, token: str | None) -> User:
    if token is None:
        raise _UNAUTHENTICATED

    parsed = read_token(token)
    if parsed is None:
        raise _UNAUTHENTICATED

    user_id, token_version = parsed
    user = await auth_service.get_by_id(session, user_id)
    if user is None or not user.is_active:
        # 禁用账号直接挡掉，不再返回具体原因
        raise _UNAUTHENTICATED
    # auth_version 不一致：旧令牌持有者已被撤销会话（重置密码/管理员撤销）
    if user.auth_version != token_version:
        raise _UNAUTHENTICATED
    return user


async def current_user(
    session: SessionDep,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> User:
    return await _user_from_token(session, token)


async def current_admin_session(
    session: SessionDep,
    token: Annotated[str | None, Cookie(alias=ADMIN_SESSION_COOKIE)] = None,
) -> User:
    """管理后台页面只认独立的后台 Cookie，不读取工作台会话。"""
    user = await _user_from_token(session, token)
    if user.role.value != "admin":
        raise _FORBIDDEN
    return user


async def admin_user(
    session: SessionDep,
    admin_token: Annotated[str | None, Cookie(alias=ADMIN_SESSION_COOKIE)] = None,
    workbench_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> User:
    """后台 API 优先读取独立后台会话，并兼容原有 API 客户端的工作台会话。"""
    user = await _user_from_token(session, admin_token or workbench_token)
    if user.role.value != "admin":
        raise _FORBIDDEN
    return user


CurrentUser = Annotated[User, Depends(current_user)]
CurrentAdminSession = Annotated[User, Depends(current_admin_session)]
AdminUser = Annotated[User, Depends(admin_user)]
