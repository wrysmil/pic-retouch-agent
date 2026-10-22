"""Rate-limit exceptions and HTTP response shape."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LimitDecision:
    allowed: bool
    scope: str
    limit: int
    remaining: int
    window_seconds: int
    reset_at_ms: int
    retry_after_ms: int

    @property
    def retry_after_seconds(self) -> int:
        return max(1, math.ceil(self.retry_after_ms / 1000))


class RateLimited(Exception):
    def __init__(
        self,
        decision: LimitDecision,
        *,
        code: str = "RATE_LIMITED",
        message: str = "请求过于频繁，请稍后再试",
    ) -> None:
        super().__init__(message)
        self.decision = decision
        self.code = code
        self.message = message

    @property
    def headers(self) -> dict[str, str]:
        retry = self.decision.retry_after_seconds
        return {
            "Retry-After": str(retry),
            "X-RateLimit-Limit": str(self.decision.limit),
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": str(math.ceil(self.decision.reset_at_ms / 1000)),
        }

    def content(self) -> dict:
        return {
            "detail": {
                "code": self.code,
                "message": self.message,
                "scope": self.decision.scope,
                "limit": self.decision.limit,
                "window_seconds": self.decision.window_seconds,
                "retry_after_seconds": self.decision.retry_after_seconds,
                "retry_after_ms": self.decision.retry_after_ms,
            }
        }


class RateLimitUnavailable(Exception):
    def __init__(self, message: str = "限流服务暂时不可用，请稍后重试") -> None:
        super().__init__(message)
        self.message = message

    @property
    def headers(self) -> dict[str, str]:
        return {"Retry-After": "5"}

    def content(self) -> dict:
        return {
            "detail": {
                "code": "RATE_LIMIT_UNAVAILABLE",
                "message": self.message,
                "retry_after_seconds": 5,
            }
        }
