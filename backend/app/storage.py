import asyncio
import base64
import hashlib
import hmac
import json
import time
from functools import lru_cache
from urllib.parse import quote

import boto3
import httpx
from botocore.client import Config
from botocore.exceptions import ClientError

from app.config import get_settings


@lru_cache
def _client(endpoint: str | None = None):
    """懒加载并缓存 S3 客户端，避免每次请求都重新创建连接。"""
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=endpoint or settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        # 七牛等 S3 兼容服务要求签名区域与桶所在区域一致
        region_name=settings.s3_region,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": settings.s3_addressing_style},
        ),
    )


def ensure_bucket() -> None:
    """幂等地确保桶存在；MinIO 未就绪时抛 ClientError，兼作健康探针。"""
    settings = get_settings()
    if not settings.s3_create_bucket:
        return
    bucket = settings.s3_bucket
    try:
        # 桶已存在则 head_bucket 成功，什么都不用做
        _client().head_bucket(Bucket=bucket)
    except ClientError:
        # 桶不存在（或 MinIO 不可达）时创建桶
        _client().create_bucket(Bucket=bucket)


@lru_cache
def _http(endpoint: str) -> httpx.Client:
    """复用到上传/外链域名的连接，避免每次上传都重新握手。"""
    return httpx.Client(timeout=120, follow_redirects=True)


def _upload_token(key: str) -> str:
    """生成七牛上传凭证（QBox token），scope 限定到单个 key。"""
    settings = get_settings()
    policy = {"scope": f"{settings.s3_bucket}:{key}", "deadline": int(time.time()) + 3600}
    encoded = base64.urlsafe_b64encode(json.dumps(policy).encode()).decode()
    sign = hmac.new(settings.s3_secret_key.encode(), encoded.encode(), hashlib.sha1).digest()
    return f"{settings.s3_access_key}:{base64.urlsafe_b64encode(sign).decode()}:{encoded}"


def _put_native(key: str, data: bytes, content_type: str) -> None:
    settings = get_settings()
    response = _http(settings.s3_upload_endpoint).post(
        settings.s3_upload_endpoint,
        data={"token": _upload_token(key), "key": key},
        files={"file": (key.rsplit("/", 1)[-1], data, content_type)},
    )
    if response.status_code != 200:
        raise RuntimeError(f"对象存储上传失败: {response.status_code} {response.text[:200]}")


def _get_public(url: str) -> bytes:
    response = _http(get_settings().s3_public_endpoint).get(url)
    response.raise_for_status()
    return response.content


def _public_url(key: str) -> str:
    settings = get_settings()
    return f"{settings.s3_public_endpoint.rstrip('/')}/{quote(key, safe='/')}"


async def put(key: str, data: bytes, content_type: str) -> None:
    """上传文件。配置了原生上传地址时走厂商通道，否则用 S3 put；均在线程池执行。"""
    if get_settings().s3_upload_endpoint:
        await asyncio.to_thread(_put_native, key, data, content_type)
        return
    await asyncio.to_thread(
        _client().put_object,
        Bucket=get_settings().s3_bucket,
        Key=key,
        Body=data,
        ContentType=content_type,
    )


async def get(key: str) -> bytes:
    """下载对象内容；公开桶优先走外链域名，避开较慢的 S3 兼容端点。"""
    settings = get_settings()
    if settings.s3_public_read and settings.s3_public_endpoint:
        return await asyncio.to_thread(_get_public, _public_url(key))
    response = await asyncio.to_thread(
        _client().get_object, Bucket=settings.s3_bucket, Key=key
    )
    return response["Body"].read()


async def delete(key: str) -> None:
    """删除对象存储中的文件。"""
    await asyncio.to_thread(_client().delete_object, Bucket=get_settings().s3_bucket, Key=key)


def signed_url(key: str) -> str:
    """浏览器可访问的对象地址。

    公开桶返回固定外链（URL 不变，浏览器可长期缓存）；私有桶退化为短时签名 URL。
    """
    settings = get_settings()
    if settings.s3_public_read and settings.s3_public_endpoint:
        return _public_url(key)
    # 用密钥对"下载该对象"的请求签名，生成一个有效期 s3_url_ttl 秒的临时直链
    return _client(settings.s3_public_endpoint or None).generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": key},
        ExpiresIn=settings.s3_url_ttl,
    )