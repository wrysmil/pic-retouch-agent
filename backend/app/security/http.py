"""HTTP security middleware and production configuration checks."""

from __future__ import annotations

import ipaddress
import logging
import re
import uuid
from urllib.parse import urlsplit

from cryptography.fernet import Fernet
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.config import Settings, get_settings
from app.security.rate_limit.policies import load_policies, validate_mode

logger = logging.getLogger(__name__)

CSP = (
    "default-src 'self'; "
    "img-src 'self' data: blob: https:; "
    "connect-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "font-src 'self'; "
    "frame-ancestors 'none'"
)
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_MUTATING = {"POST", "PUT", "PATCH", "DELETE"}


def _request_id(request: Request) -> str:
    supplied = request.headers.get("x-request-id", "").strip()
    return supplied if _REQUEST_ID_RE.fullmatch(supplied) else str(uuid.uuid4())


def _security_headers(request: Request) -> dict[str, str]:
    headers = {
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Content-Security-Policy": CSP,
        "X-Frame-Options": "DENY",
    }
    forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip()
    secure_request = request.url.scheme == "https" or forwarded_proto == "https"
    if get_settings().is_production and secure_request:
        headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return headers


def _origin_allowed(request: Request, origin: str) -> bool:
    if origin == "null":
        return False
    parsed = urlsplit(origin)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    allowed = set(get_settings().security_allowed_origins_list)
    if origin.rstrip("/") in allowed:
        return True
    own_hosts = {
        request.headers.get("host", "").strip().lower(),
        request.headers.get("x-forwarded-host", "").split(",", 1)[0].strip().lower(),
    }
    return parsed.netloc.lower() in {host for host in own_hosts if host}


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request.state.request_id = _request_id(request)
        if request.method in _MUTATING:
            fetch_site = request.headers.get("sec-fetch-site", "").strip().lower()
            origin = request.headers.get("origin")
            if fetch_site == "cross-site" or (origin and not _origin_allowed(request, origin)):
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": {
                            "code": "ORIGIN_REJECTED",
                            "message": "请求来源无效",
                        }
                    },
                    headers={
                        "X-Request-ID": request.state.request_id,
                        **_security_headers(request),
                    },
                )

        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "unhandled_request_error request_id=%s method=%s path=%s",
                request.state.request_id,
                request.method,
                request.url.path,
            )
            response = JSONResponse(
                status_code=500,
                content={
                    "detail": {
                        "code": "INTERNAL_ERROR",
                        "message": "服务器内部错误",
                        "request_id": request.state.request_id,
                    }
                },
            )

        response.headers["X-Request-ID"] = request.state.request_id
        for key, value in _security_headers(request).items():
            response.headers.setdefault(key, value)
        if response.status_code >= 500:
            logger.error(
                "server_error request_id=%s method=%s path=%s status=%s",
                request.state.request_id,
                request.method,
                request.url.path,
                response.status_code,
            )
        return response


def validate_security_config(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    mode = validate_mode(settings.rate_limit_mode)
    load_policies(settings.rate_limit_policies)

    for item in settings.trusted_proxy_ips.split(","):
        value = item.strip()
        if value:
            try:
                ipaddress.ip_network(value, strict=False)
            except ValueError as exc:
                raise RuntimeError(f"安全配置错误：TRUSTED_PROXY_IPS 含无效网段 {value}") from exc

    if not settings.is_production:
        return

    issues: list[str] = []
    if (
        settings.jwt_secret == "dev-only-secret-please-change-in-production"
        or len(settings.jwt_secret.encode("utf-8")) < 32
    ):
        issues.append("JWT_SECRET 必须替换为至少 32 字节的随机密钥")
    if not settings.secret_enc_key:
        issues.append("SECRET_ENC_KEY 未配置")
    else:
        try:
            Fernet(settings.secret_enc_key.encode("utf-8"))
        except Exception:
            issues.append("SECRET_ENC_KEY 不是合法的 Fernet key")
    if settings.s3_access_key.strip() in {"", "retouch"}:
        issues.append("S3_ACCESS_KEY 仍为开发默认值")
    if settings.s3_secret_key.strip() in {"", "retouch_dev"}:
        issues.append("S3_SECRET_KEY 仍为开发默认值")
    if mode == "off":
        issues.append("生产环境不允许关闭限流（RATE_LIMIT_MODE=off）")
    if issues:
        raise RuntimeError("生产安全配置检查失败：" + "；".join(issues))
