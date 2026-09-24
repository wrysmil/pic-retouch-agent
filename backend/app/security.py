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


def issue_token(user_id: uuid.UUID) -> str:
    settings = get_settings()
    payload = {
        # JWT 标准字段 sub（subject），存用户 ID
        "sub": str(user_id),
        # JWT 标准字段 exp（expiration），绝对过期时间
        "exp": datetime.now(UTC) + timedelta(hours=settings.jwt_ttl_hours),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALGORITHM)


def read_token(token: str) -> uuid.UUID | None:
    """解析会话令牌，任何无效情形统一返回 None 交由调用方处理为未认证。"""
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[_ALGORITHM])
        return uuid.UUID(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        # 令牌伪造/过期/结构错误时统一返回 None，调用方一律按未登录处理
        return None