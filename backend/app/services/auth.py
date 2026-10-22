"""
用户认证服务层。

提供用户注册、登录认证和用户信息查询功能。
密码使用 bcrypt 哈希存储，登录后签发 JWT 令牌。
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.security import hash_password, verify_password

# A fixed bcrypt hash makes the nonexistent-user path perform the same expensive
# password check as a real account without leaking account existence by timing.
_DUMMY_PASSWORD_HASH = (
    "$2b$12$KOpl2D4944AbJ/syiMpeOOfdMy2Y/QgT989pqEI4PSrzIuHxXGcZC"
)


class UsernameTaken(Exception):
    """用户名已被占用"""

    pass


class InvalidCredentials(Exception):
    """用户名或密码错误"""

    pass


class AccountDisabled(Exception):
    """账号已被停用"""

    pass


async def register(session: AsyncSession, username: str, password: str) -> User:
    """
    注册新用户。

    - **session**: 数据库会话
    - **username**: 用户名（需在 schema 层校验格式）
    - **password**: 明文密码（会在 security 层哈希存储）
    - **返回**: 创建的用户记录
    - **抛出**: UsernameTaken 用户名已被占用
    """
    now = datetime.now(UTC)
    user = User(
        username=username,
        password_hash=hash_password(password),
        password_changed_at=now,
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise UsernameTaken from exc
    return user


async def authenticate(session: AsyncSession, username: str, password: str) -> User:
    """
    验证用户凭证。

    - **session**: 数据库会话
    - **username**: 用户名
    - **password**: 明文密码
    - **返回**: 验证通过的用户记录
    - **抛出**: InvalidCredentials 用户名或密码错误；AccountDisabled 账号已停用
    """
    user = await session.scalar(select(User).where(User.username == username))
    if user is None:
        verify_password(password, _DUMMY_PASSWORD_HASH)
        raise InvalidCredentials
    if not verify_password(password, user.password_hash):
        raise InvalidCredentials
    if not user.is_active:
        # 区分禁用与密码错：禁用是预期内状态，对外报"账号已停用"更友好
        raise AccountDisabled
    user.last_login_at = datetime.now(UTC)
    await session.commit()
    return user


async def get_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    """
    根据 ID 获取用户。

    - **session**: 数据库会话
    - **user_id**: 用户 UUID
    - **返回**: 用户记录（不存在返回 None）
    """
    return await session.get(User, user_id)
