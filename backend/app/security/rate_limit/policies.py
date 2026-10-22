"""Rate-limit policy registry.

Policies are intentionally code-defined and can be partially overridden with
``RATE_LIMIT_POLICIES`` JSON. Invalid overrides fail fast instead of silently
disabling a limit.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

RateLimitMode = Literal["off", "shadow", "enforce"]
AllowedScope = Literal["user", "ip", "username"]
AllowedFallback = Literal["local", "closed"]


@dataclass(frozen=True, slots=True)
class ScopeLimit:
    scope: AllowedScope
    limit: int


@dataclass(frozen=True, slots=True)
class RateLimitPolicy:
    name: str
    limits: tuple[ScopeLimit, ...]
    window_seconds: int
    fallback: AllowedFallback = "closed"
    enabled: bool = True

    def limit_for(self, scope: str) -> int:
        for item in self.limits:
            if item.scope == scope:
                return item.limit
        raise KeyError(scope)


_DEFAULTS: dict[str, RateLimitPolicy] = {
    "auth-login": RateLimitPolicy(
        "auth-login", (ScopeLimit("username", 5), ScopeLimit("ip", 20)), 60
    ),
    "auth-register": RateLimitPolicy("auth-register", (ScopeLimit("ip", 3),), 3600),
    "admin-login": RateLimitPolicy(
        "admin-login", (ScopeLimit("username", 5), ScopeLimit("ip", 10)), 60
    ),
    "ai-generate": RateLimitPolicy(
        "ai-generate", (ScopeLimit("user", 5), ScopeLimit("ip", 20)), 60
    ),
    "ai-batch": RateLimitPolicy(
        "ai-batch", (ScopeLimit("user", 3), ScopeLimit("ip", 10)), 60
    ),
    "agent-plan": RateLimitPolicy(
        "agent-plan", (ScopeLimit("user", 10), ScopeLimit("ip", 30)), 60
    ),
    "editor-write": RateLimitPolicy(
        "editor-write", (ScopeLimit("user", 30), ScopeLimit("ip", 120)), 60
    ),
    "upload": RateLimitPolicy("upload", (ScopeLimit("user", 10), ScopeLimit("ip", 30)), 60),
    "delivery-preview": RateLimitPolicy(
        "delivery-preview", (ScopeLimit("user", 10), ScopeLimit("ip", 40)), 60
    ),
    "delivery-job": RateLimitPolicy(
        "delivery-job", (ScopeLimit("user", 3), ScopeLimit("ip", 10)), 60
    ),
    "delivery-retry": RateLimitPolicy(
        "delivery-retry", (ScopeLimit("user", 5), ScopeLimit("ip", 20)), 60
    ),
    "export": RateLimitPolicy("export", (ScopeLimit("user", 5), ScopeLimit("ip", 20)), 60),
    "read": RateLimitPolicy(
        "read",
        (ScopeLimit("user", 120), ScopeLimit("ip", 300)),
        60,
        fallback="local",
    ),
    # Concurrent connection slots: the window is the stale heartbeat timeout.
    "sse-connect": RateLimitPolicy(
        "sse-connect", (ScopeLimit("user", 5), ScopeLimit("ip", 20)), 90
    ),
}

_SCOPES = {"user", "ip", "username"}
_FALLBACKS = {"local", "closed"}


def _policy_from_record(name: str, value: dict, base: RateLimitPolicy | None) -> RateLimitPolicy:
    enabled = value.get("enabled", base.enabled if base else True)
    window = value.get("window_seconds", base.window_seconds if base else None)
    fallback = value.get("fallback", base.fallback if base else "closed")
    scopes = value.get("scopes", base.limits if base else None)

    if not isinstance(enabled, bool):
        raise ValueError(f"限流策略 {name} 的 enabled 必须是布尔值")
    if not isinstance(window, int) or isinstance(window, bool) or window <= 0:
        raise ValueError(f"限流策略 {name} 的 window_seconds 必须是正整数")
    if fallback not in _FALLBACKS:
        raise ValueError(f"限流策略 {name} 的 fallback 只能是 local 或 closed")

    if isinstance(scopes, dict):
        pairs = list(scopes.items())
    elif isinstance(scopes, (list, tuple)):
        pairs = []
        for item in scopes:
            if isinstance(item, ScopeLimit):
                pairs.append((item.scope, item.limit))
            elif isinstance(item, dict):
                pairs.append((item.get("scope"), item.get("limit")))
            else:
                raise ValueError(f"限流策略 {name} 的 scopes 格式无效")
    else:
        raise ValueError(f"限流策略 {name} 缺少 scopes")

    limits: list[ScopeLimit] = []
    seen: set[str] = set()
    for scope, limit in pairs:
        if scope not in _SCOPES:
            raise ValueError(f"限流策略 {name} 包含未知 scope: {scope}")
        if scope in seen:
            raise ValueError(f"限流策略 {name} 重复配置 scope: {scope}")
        if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
            raise ValueError(f"限流策略 {name}.{scope} 的 limit 必须是正整数")
        seen.add(scope)
        limits.append(ScopeLimit(scope, limit))
    if not limits:
        raise ValueError(f"限流策略 {name} 至少需要一个 scope")

    return RateLimitPolicy(name, tuple(limits), window, fallback, enabled)


@lru_cache(maxsize=8)
def load_policies(raw: str) -> dict[str, RateLimitPolicy]:
    policies = dict(_DEFAULTS)
    if not raw.strip():
        return policies

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"RATE_LIMIT_POLICIES 不是合法 JSON: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise ValueError("RATE_LIMIT_POLICIES 必须是对象")

    for name, override in payload.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("限流策略名不能为空")
        if not isinstance(override, dict):
            raise ValueError(f"限流策略 {name} 必须是对象")
        base = policies.get(name)
        if base is None:
            raise ValueError(f"未知限流策略：{name}（新增策略需先在代码注册）")
        policies[name] = _policy_from_record(name, override, base)
    return policies


def policy_of(name: str, raw_overrides: str = "") -> RateLimitPolicy:
    policies = load_policies(raw_overrides)
    try:
        return policies[name]
    except KeyError as exc:
        raise ValueError(f"限流策略未配置：{name}") from exc


def validate_mode(mode: str) -> RateLimitMode:
    if mode not in {"off", "shadow", "enforce"}:
        raise ValueError("RATE_LIMIT_MODE 只能是 off、shadow 或 enforce")
    return mode  # type: ignore[return-value]
