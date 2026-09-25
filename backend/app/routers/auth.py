"""
认证相关接口。

提供用户注册、登录、登出和获取当前用户信息的功能。
"""

from fastapi import APIRouter, HTTPException, Response, status

from app.config import get_settings
from app.db import SessionDep
from app.deps import CurrentUser
from app.models import User
from app.schemas.auth import Credentials, UserOut
from app.security import SESSION_COOKIE, issue_token
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _start_session(response: Response, user: User) -> UserOut:
    """创建会话：设置 Cookie 并返回用户信息。"""
    settings = get_settings()
    response.set_cookie(
        SESSION_COOKIE,
        issue_token(user.id),
        max_age=settings.jwt_ttl_hours * 3600,
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
        path="/",
    )
    return UserOut.model_validate(user)


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    summary="用户注册",
    description="创建新用户账号，注册成功后自动登录。",
)
async def register(
    credentials: Credentials,
    response: Response,
    session: SessionDep,
) -> UserOut:
    """
    注册新用户。

    - **credentials.username**: 用户名（3-32字符）
    - **credentials.password**: 密码（6-128字符）
    - **返回**: 注册用户的详细信息

    **可能错误**:
    - 409: 用户名已被占用
    """
    try:
        user = await auth_service.register(session, credentials.username, credentials.password)
    except auth_service.UsernameTaken:
        raise HTTPException(status.HTTP_409_CONFLICT, "该用户名已被占用") from None
    return _start_session(response, user)


@router.post(
    "/login",
    summary="用户登录",
    description="使用用户名密码登录，登录成功后设置会话 Cookie。",
)
async def login(
    credentials: Credentials,
    response: Response,
    session: SessionDep,
) -> UserOut:
    """
    用户登录。

    - **credentials.username**: 用户名
    - **credentials.password**: 密码
    - **返回**: 登录用户的详细信息

    **可能错误**:
    - 401: 用户名或密码错误
    """
    try:
        user = await auth_service.authenticate(session, credentials.username, credentials.password)
    except auth_service.InvalidCredentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户名或密码错误") from None
    return _start_session(response, user)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="用户登出",
    description="清除会话 Cookie，结束当前登录状态。",
)
async def logout(response: Response) -> None:
    """
    用户登出。

    清除会话 Cookie，无返回值。
    """
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get(
    "/me",
    summary="获取当前用户",
    description="获取已登录用户的详细信息。",
)
async def me(user: CurrentUser) -> UserOut:
    """
    获取当前登录用户信息。

    - **返回**: 当前用户的详细信息

    **可能错误**:
    - 401: 未登录
    """
    return UserOut.model_validate(user)