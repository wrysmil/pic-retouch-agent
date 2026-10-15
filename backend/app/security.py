import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.config import get_settings

# 前端会话 Cookie 的名字
SESSION_COOKIE = "session"
# JWT 签名算法，H256 是对称密钥，加解密用同一个 jwt_secret
_ALGORITHM = "HS256"


def hash_password(plain: str) -> str:
    # bcrypt 自动生成随机盐并混入结果中，同一明文每次哈希结果不同
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    # 从 hashed 中取出盐重新计算对比，校验明文是否匹配哈希
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def issue_token(user_id: uuid.UUID, auth_version: int) -> str:
    """签发带 auth_version 的会话令牌。

    auth_version 来自数据库，每次重置密码或撤销会话都会递增，
    这样旧 JWT 的版本号自然就匹配不上，用户必须重新登录。
    """
    settings = get_settings()
    payload = {
        # JWT 标准字段 sub（subject），存用户 ID
        "sub": str(user_id),
        # 自定义字段 av（auth version），与数据库比对，任意操作导致版本递增都会作废旧令牌
        "auth_version": auth_version,
        # JWT 标准字段 exp（expiration），绝对过期时间
        "exp": datetime.now(UTC) + timedelta(hours=settings.jwt_ttl_hours),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALGORITHM)


def read_token(token: str) -> tuple[uuid.UUID, int] | None:
    """解析会话令牌，返回 (用户 ID, auth_version)。任意无效情形统一返回 None。

    auth_version 还需要去数据库比对一次才能确认是否被撤销，单看这里只能验证签名/过期。
    """
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[_ALGORITHM])
        return uuid.UUID(payload["sub"]), int(payload.get("auth_version", 0))
    except (jwt.InvalidTokenError, KeyError, ValueError):
        # 令牌伪造/过期/结构错误时统一返回 None，调用方一律按未登录处理
        return None