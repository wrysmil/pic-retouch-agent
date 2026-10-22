"""FastAPI dependencies for route-level rate limits."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import HTTPException, Request, Response, status

from app.config import get_settings
from app.security.rate_limit.limiter import check_rate_limit
from app.security.rate_limit.policies import policy_of

MAX_UPLOAD_REQUEST_BYTES = 21 * 1024 * 1024
_READ_EXEMPT = {"/api/health", "/api/docs", "/api/openapi.json"}


def rate_limit(policy_name: str) -> Callable[..., Awaitable[None]]:
    async def dependency(request: Request, response: Response) -> None:
        settings = get_settings()
        policy = policy_of(policy_name, settings.rate_limit_policies)
        username: str | None = None
        if any(item.scope == "username" for item in policy.limits):
            try:
                body = await request.json()
            except Exception:
                body = None
            if isinstance(body, dict) and isinstance(body.get("username"), str):
                username = body["username"]
        await check_rate_limit(request, policy, username=username, response=response)

    dependency.__name__ = f"rate_limit_{policy_name.replace('-', '_')}"
    return dependency


async def read_rate_limit(request: Request, response: Response) -> None:
    """Apply one policy to all ordinary reads, regardless of UUID in the URL."""
    if request.method not in {"GET", "HEAD"}:
        return
    if request.url.path in _READ_EXEMPT:
        return
    settings = get_settings()
    policy = policy_of("read", settings.rate_limit_policies)
    await check_rate_limit(request, policy, response=response)


async def upload_rate_limit(request: Request, response: Response) -> None:
    """Reject clearly oversized multipart bodies before FastAPI parses them."""
    raw_length = request.headers.get("content-length")
    if raw_length:
        try:
            length = int(raw_length)
        except ValueError:
            length = 0
        if length > MAX_UPLOAD_REQUEST_BYTES:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                "文件超过 20 MB 上限",
            )

    settings = get_settings()
    policy = policy_of("upload", settings.rate_limit_policies)
    await check_rate_limit(request, policy, response=response)
