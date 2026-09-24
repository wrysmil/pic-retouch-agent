import asyncio
from functools import lru_cache

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.config import get_settings


@lru_cache
def _client():
    """懒加载并缓存 S3 客户端，避免每次请求都重新创建连接。"""
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def ensure_bucket() -> None:
    """幂等地确保桶存在；MinIO 未就绪时抛 ClientError，兼作健康探针。"""
    bucket = get_settings().s3_bucket
    try:
        # 桶已存在则 head_bucket 成功，什么都不用做
        _client().head_bucket(Bucket=bucket)
    except ClientError:
        # 桶不存在（或 MinIO 不可达）时创建桶
        _client().create_bucket(Bucket=bucket)


async def put(key: str, data: bytes, content_type: str) -> None:
    """上传文件到对象存储。boto3 是同步阻塞的，丢到线程池执行，避免卡住事件循环。"""
    await asyncio.to_thread(
        _client().put_object,
        Bucket=get_settings().s3_bucket,
        Key=key,
        Body=data,
        ContentType=content_type,
    )


async def get(key: str) -> bytes:
    """从对象存储下载文件内容（返回原始字节）。"""
    response = await asyncio.to_thread(
        _client().get_object, Bucket=get_settings().s3_bucket, Key=key
    )
    return response["Body"].read()


async def delete(key: str) -> None:
    """删除对象存储中的文件。"""
    await asyncio.to_thread(_client().delete_object, Bucket=get_settings().s3_bucket, Key=key)


def signed_url(key: str) -> str:
    """生成短时签名 URL。纯本地计算，不产生网络请求。"""
    settings = get_settings()
    # 用密钥对"下载该对象"的请求签名，生成一个有效期 s3_url_ttl 秒的临时直链
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": key},
        ExpiresIn=settings.s3_url_ttl,
    )