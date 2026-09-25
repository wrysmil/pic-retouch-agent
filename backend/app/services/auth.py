"""
用户认证服务层。

提供用户注册、登录认证和用户信息查询功能。
密码使用 bcrypt 哈希存储，登录后签发 JWT 令牌。
"""

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.security import hash_password, verify_password


class UsernameTaken(Exception):
    """用户名已被占用"""

    pass


class InvalidCredentials(Exception):
    """用户名或密码错误"""

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
    user = User(username=username, password_hash=hash_password(password))
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
    - **抛出**: InvalidCredentials 用户名不存在或密码错误
    """
    user = await session.scalar(select(User).where(User.username == username))
    if user is None or not verify_password(password, user.password_hash):
        raise InvalidCredentials
    return user


async def get_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    """
    根据 ID 获取用户。

    - **session**: 数据库会话
    - **user_id**: 用户 UUID
    - **返回**: 用户记录（不存在返回 None）
    """
    return await session.get(User, user_id)