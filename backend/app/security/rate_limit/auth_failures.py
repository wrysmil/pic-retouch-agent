"""Short-lived login failure counters independent from request-rate limits."""

from __future__ import annotations

import hashlib
import time

from fastapi import Request
from redis.exceptions import RedisError

from app.config import get_settings
from app.security.rate_limit.errors import LimitDecision, RateLimited, RateLimitUnavailable
from app.security.rate_limit.identity import client_ip, username_fingerprint
from app.security.rate_limit.limiter import redis_client

_INCR_SCRIPT = r"""
local current = redis.call('INCR', KEYS[1])
if current == 1 then
  redis.call('PEXPIRE', KEYS[1], ARGV[1])
end
return current
"""


def _prefix(admin: bool) -> str:
    return "auth:fail:admin" if admin else "auth:fail:user"


def _user_key(admin: bool, username: str) -> str:
    return f"{_prefix(admin)}:{username_fingerprint(username)}"


def _ip_key(admin: bool, ip: str) -> str:
    fingerprint = hashlib.sha256(ip.encode("utf-8")).hexdigest()[:16]
    return f"{_prefix(admin)}:ip:{fingerprint}"


async def assert_login_allowed(request: Request, username: str, *, admin: bool = False) -> None:
    settings = get_settings()
    if settings.rate_limit_mode == "off":
        return
    window = settings.auth_failure_window_seconds
    limit = settings.auth_failure_limit
    keys = (_user_key(admin, username), _ip_key(admin, client_ip(request)))
    try:
        raw = await redis_client().mget(*keys)
        counts = [int(value or 0) for value in raw]
        if max(counts, default=0) < limit:
            return
        ttls = (await redis_client().ttl(keys[0]), await redis_client().ttl(keys[1]))
        retry = max(1, max((value for value in ttls if value > 0), default=window))
    except (RedisError, OSError, TimeoutError, ValueError) as exc:
        if settings.rate_limit_mode == "enforce":
            raise RateLimitUnavailable("登录保护服务暂时不可用，请稍后重试") from exc
        return

    scope = "username" if counts[0] >= limit else "ip"
    decision = LimitDecision(
        allowed=False,
        scope=scope,
        limit=limit,
        remaining=0,
        window_seconds=window,
        reset_at_ms=int((time.time() + retry) * 1000),
        retry_after_ms=retry * 1000,
    )
    if settings.rate_limit_mode == "enforce":
        raise RateLimited(
            decision,
            code="AUTH_LOCKED",
            message="登录尝试次数过多，请稍后再试",
        )


async def record_login_failure(request: Request, username: str, *, admin: bool = False) -> None:
    if get_settings().rate_limit_mode == "off":
        return
    ttl_ms = get_settings().auth_failure_window_seconds * 1000
    keys = (_user_key(admin, username), _ip_key(admin, client_ip(request)))
    try:
        for key in keys:
            await redis_client().eval(_INCR_SCRIPT, 1, key, ttl_ms)
    except (RedisError, OSError, TimeoutError) as exc:
        if get_settings().rate_limit_mode == "enforce":
            raise RateLimitUnavailable("登录保护服务暂时不可用，请稍后重试") from exc
        return


async def clear_login_failures(username: str, *, admin: bool = False) -> None:
    if get_settings().rate_limit_mode == "off":
        return
    try:
        await redis_client().delete(_user_key(admin, username))
    except (RedisError, OSError, TimeoutError):
        # A successful credential check must not be turned into a login failure
        # because the best-effort cleanup could not reach Redis.
        return
