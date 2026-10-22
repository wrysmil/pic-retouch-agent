"""Identity extraction for rate-limit buckets.

The limiter intentionally reads the signed JWT directly instead of querying the
database. Revoked users still consume their old user bucket, which is the safer
failure mode for abuse protection.
"""

from __future__ import annotations

import hashlib
import ipaddress
from functools import lru_cache

from fastapi import Request

from app.config import get_settings
from app.security import ADMIN_SESSION_COOKIE, SESSION_COOKIE, read_token


def _parse_ip(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    text = value.strip()
    if not text:
        return None
    if text.startswith("[") and "]" in text:
        text = text[1 : text.index("]")]
    elif text.count(":") == 1 and "." in text:
        # IPv4 with a port. Bare IPv6 values contain multiple colons and must
        # not be split here.
        text = text.rsplit(":", 1)[0]
    try:
        return ipaddress.ip_address(text)
    except ValueError:
        return None


@lru_cache(maxsize=8)
def _trusted_networks(raw: str) -> tuple[ipaddress._BaseNetwork, ...]:
    networks: list[ipaddress._BaseNetwork] = []
    for item in raw.split(","):
        value = item.strip()
        if not value:
            continue
        try:
            networks.append(ipaddress.ip_network(value, strict=False))
        except ValueError:
            # Production startup validation catches this before traffic. In
            # development, logging a bad entry is safer than trusting it.
            continue
    return tuple(networks)


def _is_trusted(ip: ipaddress._BaseAddress, networks: tuple[ipaddress._BaseNetwork, ...]) -> bool:
    return any(ip in network for network in networks)


def _normalize(ip: ipaddress._BaseAddress) -> str:
    if isinstance(ip, ipaddress.IPv6Address):
        # /64 aggregation prevents trivial rotation within one customer prefix.
        network = ipaddress.ip_network(f"{ip}/64", strict=False)
        return str(network.network_address)
    return str(ip)


def client_ip(request: Request) -> str:
    settings = get_settings()
    peer = _parse_ip(request.client.host) if request.client else None
    trusted = _trusted_networks(settings.trusted_proxy_ips)

    chosen = peer
    if peer is not None and trusted and _is_trusted(peer, trusted):
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            for raw in reversed([item.strip() for item in forwarded.split(",")]):
                candidate = _parse_ip(raw)
                if candidate is None:
                    continue
                if not _is_trusted(candidate, trusted):
                    chosen = candidate
                    break

    if chosen is None:
        return "unknown"
    return _normalize(chosen)


def user_id_from_request(request: Request) -> str | None:
    for name in (SESSION_COOKIE, ADMIN_SESSION_COOKIE):
        token = request.cookies.get(name)
        if not token:
            continue
        parsed = read_token(token)
        if parsed is not None:
            return str(parsed[0])
    return None


def normalize_username(username: str) -> str:
    return username.strip().casefold()


def username_fingerprint(username: str) -> str:
    normalized = normalize_username(username)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
