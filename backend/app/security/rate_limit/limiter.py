"""Redis-backed sliding-window limiter with a bounded local read fallback."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
import uuid
from collections import OrderedDict, deque
from dataclasses import dataclass

from fastapi import Request, Response
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.config import get_settings
from app.security.rate_limit.errors import LimitDecision, RateLimited, RateLimitUnavailable
from app.security.rate_limit.identity import client_ip, user_id_from_request, username_fingerprint
from app.security.rate_limit.lua import SLIDING_WINDOW_SCRIPT, SSE_SLOT_SCRIPT, parse_result
from app.security.rate_limit.policies import RateLimitPolicy, policy_of

logger = logging.getLogger(__name__)

_redis: Redis | None = None


def redis_client() -> Redis:
    global _redis
    if _redis is None:
        settings = get_settings()
        _redis = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=settings.rate_limit_redis_timeout_seconds,
            socket_timeout=settings.rate_limit_redis_timeout_seconds,
        )
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


def _prefix() -> str:
    return get_settings().rate_limit_key_prefix.strip(":") or "rl"


def _identity_keys(
    policy: RateLimitPolicy,
    request: Request,
    username: str | None,
) -> list[tuple[str, str]]:
    user_id = user_id_from_request(request)
    ip = client_ip(request)
    values = {
        "user": user_id,
        "ip": ip,
        "username": username_fingerprint(username) if username else None,
    }
    keys: list[tuple[str, str]] = []
    for item in policy.limits:
        identity = values.get(item.scope)
        if not identity:
            continue
        keys.append(
            (
                item.scope,
                f"{_prefix()}:{policy.name}:{policy.window_seconds}:{item.scope}:{identity}",
            )
        )
    return keys


def _request_member(request: Request) -> str:
    # The request id may come from a client header, so it cannot be the sole
    # ZSET member: reusing one id would update the same member and never grow
    # the window count. Keep the id for log correlation and add entropy.
    request_id = getattr(request.state, "request_id", None) or "-"
    return f"{request_id}:{uuid.uuid4().hex}"


def _decision(
    raw: list | tuple,
    keys: list[tuple[str, str]],
    policy: RateLimitPolicy,
) -> LimitDecision:
    parsed = parse_result(raw)
    scope = keys[parsed.scope_index - 1][0] if parsed.scope_index else keys[0][0]
    return LimitDecision(
        allowed=parsed.allowed,
        scope=scope,
        limit=parsed.limit,
        remaining=parsed.remaining,
        window_seconds=policy.window_seconds,
        reset_at_ms=parsed.reset_at_ms,
        retry_after_ms=parsed.retry_after_ms,
    )


def set_rate_limit_headers(response: Response | None, decision: LimitDecision) -> None:
    if response is None:
        return
    retry = decision.retry_after_seconds if not decision.allowed else 0
    response.headers["X-RateLimit-Limit"] = str(decision.limit)
    response.headers["X-RateLimit-Remaining"] = str(max(0, decision.remaining))
    response.headers["X-RateLimit-Reset"] = str((decision.reset_at_ms + 999) // 1000)
    if retry:
        response.headers["Retry-After"] = str(retry)


async def check_rate_limit(
    request: Request,
    policy: RateLimitPolicy,
    *,
    username: str | None = None,
    response: Response | None = None,
) -> LimitDecision | None:
    settings = get_settings()
    mode = settings.rate_limit_mode
    if mode == "off" or not policy.enabled:
        return None

    keys = _identity_keys(policy, request, username)
    if not keys:
        fallback = next(item for item in policy.limits if item.scope == "ip")
        keys = [
            (
                "ip",
                f"{_prefix()}:{policy.name}:{policy.window_seconds}:ip:{client_ip(request)}",
            )
        ]
        limits = [fallback.limit]
    else:
        limits = [policy.limit_for(scope) for scope, _ in keys]

    member = _request_member(request)
    try:
        raw = await redis_client().eval(
            SLIDING_WINDOW_SCRIPT,
            len(keys),
            *(key for _, key in keys),
            policy.window_seconds * 1000,
            member,
            *limits,
        )
        decision = _decision(raw, keys, policy)
    except (RedisError, OSError, TimeoutError, ValueError) as exc:
        logger.warning(
            "rate_limit_redis_error request_id=%s policy=%s error=%s",
            getattr(request.state, "request_id", "-"),
            policy.name,
            type(exc).__name__,
        )
        if mode == "shadow":
            return None
        if policy.fallback == "local":
            decision = await _local_check(keys, limits, policy)
        else:
            raise RateLimitUnavailable from exc

    set_rate_limit_headers(response, decision)
    if not decision.allowed:
        logger.warning(
            "rate_limit_hit request_id=%s policy=%s scope=%s limit=%s retry_after=%s mode=%s",
            getattr(request.state, "request_id", "-"),
            policy.name,
            decision.scope,
            decision.limit,
            decision.retry_after_seconds,
            mode,
        )
        if mode == "enforce":
            raise RateLimited(decision)
    return decision


@dataclass
class _LocalState:
    hits: deque[float]


_local: OrderedDict[str, _LocalState] = OrderedDict()
_local_lock = asyncio.Lock()


async def _local_check(
    keys: list[tuple[str, str]],
    limits: list[int],
    policy: RateLimitPolicy,
) -> LimitDecision:
    now = time.time()
    window = policy.window_seconds
    cutoff = now - window
    max_buckets = get_settings().rate_limit_local_buckets
    async with _local_lock:
        while len(_local) > max_buckets:
            _local.popitem(last=False)
            logger.warning("rate_limit_local_evict policy=%s", policy.name)

        scanned: list[tuple[str, _LocalState, int, int]] = []
        denied: tuple[str, int, float] | None = None
        for (scope, key), limit in zip(keys, limits, strict=True):
            state = _local.get(key)
            if state is None:
                state = _LocalState(deque())
                _local[key] = state
            while state.hits and state.hits[0] <= cutoff:
                state.hits.popleft()
            _local.move_to_end(key)
            remaining = limit - len(state.hits)
            if remaining <= 0:
                retry = (state.hits[0] + window - now) if state.hits else window
                denied = (scope, limit, retry)
                break
            scanned.append((scope, state, limit, remaining))

        if denied is not None:
            scope, limit, retry = denied
            logger.warning(
                "rate_limit_local_fallback_denied policy=%s scope=%s", policy.name, scope
            )
            return LimitDecision(
                allowed=False,
                scope=scope,
                limit=limit,
                remaining=0,
                window_seconds=window,
                reset_at_ms=int((now + retry) * 1000),
                retry_after_ms=max(0, int(retry * 1000)),
            )

        minimum_remaining = min((item[3] - 1 for item in scanned), default=0)
        for _, state, _, _ in scanned:
            state.hits.append(now)
        return LimitDecision(
            allowed=True,
            scope=scanned[0][0] if scanned else "ip",
            limit=scanned[0][2] if scanned else 0,
            remaining=minimum_remaining,
            window_seconds=window,
            reset_at_ms=int((now + window) * 1000),
            retry_after_ms=0,
        )


@dataclass
class SSELease:
    keys: tuple[str, ...]
    member: str

    async def touch(self) -> None:
        now = int(time.time() * 1000)
        try:
            pipeline = redis_client().pipeline(transaction=False)
            for key in self.keys:
                pipeline.zadd(key, {self.member: now})
            await pipeline.execute()
        except (RedisError, OSError, TimeoutError):
            logger.warning("sse_slot_touch_failed member=%s", self.member)

    async def release(self) -> None:
        try:
            pipeline = redis_client().pipeline(transaction=False)
            for key in self.keys:
                pipeline.zrem(key, self.member)
            await pipeline.execute()
        except (RedisError, OSError, TimeoutError):
            logger.warning("sse_slot_release_failed member=%s", self.member)


async def acquire_sse_slot(request: Request) -> SSELease | None:
    settings = get_settings()
    policy = policy_of("sse-connect", settings.rate_limit_policies)
    if settings.rate_limit_mode == "off" or not policy.enabled:
        return None

    keys = _identity_keys(policy, request, None)
    if not keys:
        keys = [
            (
                "ip",
                f"{_prefix()}:sse-connect:{policy.window_seconds}:ip:{client_ip(request)}",
            )
        ]
    limits = [policy.limit_for(scope) for scope, _ in keys]
    member = f"{_request_member(request)}:{uuid.uuid4().hex[:8]}"
    enforce = 1 if settings.rate_limit_mode == "enforce" else 0
    try:
        raw = await redis_client().eval(
            SSE_SLOT_SCRIPT,
            len(keys),
            *(key for _, key in keys),
            policy.window_seconds,
            member,
            enforce,
            *limits,
        )
        decision = _decision(raw, keys, policy)
    except (RedisError, OSError, TimeoutError, ValueError) as exc:
        logger.warning(
            "sse_slot_redis_error request_id=%s error=%s",
            getattr(request.state, "request_id", "-"),
            type(exc).__name__,
        )
        if settings.rate_limit_mode == "shadow":
            return None
        raise RateLimitUnavailable from exc

    if not decision.allowed and settings.rate_limit_mode == "enforce":
        raise RateLimited(
            decision,
            code="SSE_CONNECTION_LIMIT",
            message="同时进行的实时连接过多，请关闭其他页面后重试",
        )
    return SSELease(tuple(key for _, key in keys), member)


def anonymous_fingerprint(value: str) -> str:
    """Stable short identifier for logs without storing raw IPs/usernames."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
