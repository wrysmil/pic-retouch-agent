"""API Key / 厂商凭证的加密存储。

主密钥从 SECRET_ENC_KEY 读取，期望是经过 base64-urlsafe 编码的 32 字节随机串。
本地开发未配置时进入"明文直通"分支，但仅供 `allow_local_provider_hosts` 真值时使用，
生产环境必须显式配置，否则调用 encrypt 时直接抛错。
"""

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


class EncryptionUnavailable(Exception):
    """主密钥未配置，无法做加密写。"""


class DecryptionFailed(Exception):
    """解密失败，可能是主密钥轮换或数据被外部篡改。"""


def _fernet() -> Fernet | None:
    key = get_settings().secret_enc_key
    if not key:
        return None
    return Fernet(key.encode())


def encrypt_secret(plain: str) -> str:
    f = _fernet()
    if f is None:
        raise EncryptionUnavailable("未配置 SECRET_ENC_KEY，禁止保存厂商凭证")
    return f.encrypt(plain.encode()).decode()


def decrypt_secret(cipher: str) -> str:
    f = _fernet()
    if f is None:
        # 配置丢失但库里还有密文：宁愿读不到也不能误把空串当合法凭证
        raise DecryptionFailed("服务器未配置 SECRET_ENC_KEY，无法读取已保存的密钥")
    try:
        return f.decrypt(cipher.encode()).decode()
    except InvalidToken as exc:
        raise DecryptionFailed("厂商凭证解密失败") from exc


def mask_secret(plain: str) -> str:
    """仅显示尾号，避免在 API 响应里把密钥泄给前端。"""
    if not plain:
        return ""
    if len(plain) <= 4:
        return "****"
    return f"****{plain[-4:]}"