"""厂商接入地址校验。

白名单来自配置项；开发环境显式启用后允许任意本地地址。
线上环境强制 HTTPS + 域名在白名单内；解析到私网 / 环回 / 元数据地址也拒绝。
"""

from ipaddress import ip_address
from urllib.parse import urlparse

from app.config import get_settings


class ProviderUrlRejected(Exception):
    """厂商地址不符合策略。"""


_PRIVATE_NETS = (
    "127.0.0.0/8",
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "169.254.0.0/16",  # 云元数据
    "::1/128",
    "fc00::/7",
)


def validate_provider_url(url: str) -> str:
    """校验通过返回规范化后的 url；不符合策略抛出 ProviderUrlRejected。"""
    settings = get_settings()
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        raise ProviderUrlRejected("厂商地址必须使用 http(s) 协议")
    host = (parsed.hostname or "").lower()
    if not host:
        raise ProviderUrlRejected("厂商地址缺少主机名")

    if settings.allow_local_provider_hosts:
        # 开发期放行任意地址（包含本地 / 私网）。生产环境不应进入此分支。
        return parsed.geturl()

    if parsed.scheme != "https":
        raise ProviderUrlRejected("生产环境厂商地址必须使用 HTTPS")

    allowlist = settings.provider_host_allowlist
    if allowlist and host not in allowlist:
        raise ProviderUrlRejected(f"厂商主机名 {host} 不在可信列表")

    try:
        addr = ip_address(host)
    except ValueError:
        # 域名形式：不解析 IP，信任白名单
        return parsed.geturl()

    for net in _PRIVATE_NETS:
        if addr in __import__("ipaddress").ip_network(net):
            raise ProviderUrlRejected("厂商主机名解析到私网或元数据地址")
    return parsed.geturl()