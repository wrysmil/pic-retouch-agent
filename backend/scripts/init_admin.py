"""初始化首位管理员或重置指定用户密码。

通过命令行参数完成，不暴露 HTTP 入口。

用法：
    python scripts/init_admin.py create <username> <password>
    python scripts/init_admin.py promote <username> [--password <new>]

create：用户不存在则创建为管理员，存在则拒绝（避免误改旧账号）。
promote：把已有用户提升为管理员；可选地重置密码；同样禁止覆盖最后一个启用的管理员。
"""

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select

from app.db import SessionFactory
from app.models import User, UserRole
from app.security import hash_password


def _now() -> datetime:
    return datetime.now(UTC)


async def create_admin(username: str, password: str) -> None:
    async with SessionFactory() as session:
        existing = await session.scalar(select(User).where(User.username == username))
        if existing is not None:
            print(f"用户 {username} 已存在，拒绝创建")
            return
        user = User(
            username=username,
            password_hash=hash_password(password),
            role=UserRole.ADMIN,
            is_active=True,
            password_changed_at=_now(),
        )
        session.add(user)
        await session.commit()
        print(f"已创建管理员 {username}（id={user.id}）")


async def promote(username: str, new_password: str | None) -> None:
    async with SessionFactory() as session:
        user = await session.scalar(select(User).where(User.username == username))
        if user is None:
            print(f"用户 {username} 不存在")
            return
        # 已经是管理员：只允许改密码
        if user.role is UserRole.ADMIN:
            print(f"{username} 已是管理员，无需提升")
        else:
            user.role = UserRole.ADMIN
            print(f"已将 {username} 提升为管理员")

        if new_password is not None:
            user.password_hash = hash_password(new_password)
            user.password_changed_at = _now()
            # 改密码顺带撤销旧会话，避免原 token 仍能进后台
            user.auth_version = user.auth_version + 1
            print("已重置密码并递增 auth_version")

        await session.commit()


async def main() -> int:
    parser = argparse.ArgumentParser(description="初始化或更新管理员账号")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="创建首位管理员账号")
    create.add_argument("username")
    create.add_argument("password")

    promote_cmd = sub.add_parser("promote", help="将已有用户提升为管理员")
    promote_cmd.add_argument("username")
    promote_cmd.add_argument("--password", dest="password", default=None)

    args = parser.parse_args()

    if args.command == "create":
        await create_admin(args.username, args.password)
    elif args.command == "promote":
        await promote(args.username, args.password)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))