"""模型运行期：根据发布版本构造文字与图像客户端。

客户端按 (版本 id, 能力) 缓存；旧版本随引用计数归零后被替换。
"""

import asyncio
import uuid
from dataclasses import dataclass
from typing import Any

from langchain_openai import ChatOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AdapterType,
    ModelConnection,
    ModelConnectionVersion,
    ModelDefinition,
    RuntimeConfigVersion,
)
from app.providers.base import ImageProvider
from app.providers.dashscope import DashScopeImageProvider
from app.providers.mock import MockImageProvider
from app.providers.openai_image import OpenAIImageProvider
from app.security_vault import decrypt_secret, DecryptionFailed
from app.services import model_config


_COMPAT_PATH = "/compatible-mode/v1"


@dataclass(frozen=True)
class PlannerClient:
    """文字规划客户端及版本引用，避免后续修改时改到别的版本。"""

    version: RuntimeConfigVersion
    model_definition: ModelDefinition
    connection_version: ModelConnectionVersion
    connection: ModelConnection
    api_key: str
    base_url: str
    client: ChatOpenAI


@dataclass(frozen=True)
class ImageClient:
    """图像客户端：单一生图模型 + 其连接版本。编辑复用同模型或 edit_vendor_model_id。"""

    version: RuntimeConfigVersion
    image_def: ModelDefinition
    image_conn_version: ModelConnectionVersion
    provider: ImageProvider


class RuntimeMissing(Exception):
    """当前还没有发布的运行配置。"""


class IncompatibleRuntime(Exception):
    """当前运行配置与请求的能力不匹配。"""


class PlannerClientCache:
    """以版本 id 为键缓存 ChatOpenAI 实例，版本被替换后旧实例自然出缓存。"""

    def __init__(self) -> None:
        self._by_version: dict[uuid.UUID, PlannerClient] = {}
        self._lock = asyncio.Lock()

    def clear(self) -> None:
        self._by_version.clear()

    async def get(self, session: AsyncSession, version_id: uuid.UUID) -> PlannerClient:
        cached = self._by_version.get(version_id)
        if cached is not None:
            return cached
        async with self._lock:
            cached = self._by_version.get(version_id)
            if cached is not None:
                return cached
            client = await _build_planner(session, version_id)
            self._by_version[version_id] = client
            return client


class ImageClientCache:
    def __init__(self) -> None:
        self._by_version: dict[uuid.UUID, ImageClient] = {}
        self._lock = asyncio.Lock()

    def clear(self) -> None:
        self._by_version.clear()

    async def get(self, session: AsyncSession, version_id: uuid.UUID) -> ImageClient:
        cached = self._by_version.get(version_id)
        if cached is not None:
            return cached
        async with self._lock:
            cached = self._by_version.get(version_id)
            if cached is not None:
                return cached
            client = await _build_image(session, version_id)
            self._by_version[version_id] = client
            return client


_planner_cache = PlannerClientCache()
_image_cache = ImageClientCache()


def planner_cache() -> PlannerClientCache:
    return _planner_cache


def image_cache() -> ImageClientCache:
    return _image_cache


async def current_version_id(session: AsyncSession) -> uuid.UUID:
    """解析当前生效版本，未发布时抛 RuntimeMissing。"""
    version = await model_config.get_current_version(session)
    if version is None:
        raise RuntimeMissing("尚未发布运行配置")
    return version.id


async def get_planner(session: AsyncSession, version_id: uuid.UUID) -> PlannerClient:
    return await _planner_cache.get(session, version_id)


async def get_image_client(session: AsyncSession, version_id: uuid.UUID) -> ImageClient:
    return await _image_cache.get(session, version_id)


async def _build_planner(session: AsyncSession, version_id: uuid.UUID) -> PlannerClient:
    version = await session.get(RuntimeConfigVersion, version_id)
    if version is None:
        raise RuntimeMissing("指定的运行版本不存在")

    model_def = await session.get(ModelDefinition, version.text_model_id)
    if model_def is None:
        raise IncompatibleRuntime("文本模型不存在")
    conn_version = await session.get(ModelConnectionVersion, version.text_connection_version_id)
    if conn_version is None:
        raise IncompatibleRuntime("文本连接版本不存在")
    if conn_version.revoked:
        raise IncompatibleRuntime("文本连接版本已被撤销")

    conn = await session.get(ModelConnection, model_def.connection_id)
    if conn is None:
        raise IncompatibleRuntime("文本连接不存在")

    api_key = _decrypt_key(conn_version)
    base_url = conn_version.base_url
    chat = ChatOpenAI(
        model=model_def.vendor_model_id,
        api_key=api_key,
        base_url=_resolve_planner_base(conn.adapter_type, base_url),
        temperature=0,
    )
    return PlannerClient(
        version=version,
        model_definition=model_def,
        connection_version=conn_version,
        connection=conn,
        api_key=api_key,
        base_url=base_url,
        client=chat,
    )


async def _build_image(session: AsyncSession, version_id: uuid.UUID) -> ImageClient:
    version = await session.get(RuntimeConfigVersion, version_id)
    if version is None:
        raise RuntimeMissing("指定的运行版本不存在")

    image_def = await session.get(ModelDefinition, version.image_model_id)
    image_cv = await session.get(ModelConnectionVersion, version.image_connection_version_id)
    if None in (image_def, image_cv):
        raise IncompatibleRuntime("运行配置不完整")

    if image_cv.revoked:
        raise IncompatibleRuntime("生图连接版本已被撤销")

    image_conn = await session.get(ModelConnection, image_def.connection_id)
    if image_conn is None:
        raise IncompatibleRuntime("图像连接不存在")

    provider = _build_image_provider(
        image_conn.adapter_type,
        image_cv,
        image_def.vendor_model_id,
        image_def.edit_vendor_model_id,
    )
    return ImageClient(
        version=version,
        image_def=image_def,
        image_conn_version=image_cv,
        provider=provider,
    )


def _resolve_planner_base(adapter: AdapterType, base_url: str) -> str:
    """不同文字协议的 base URL 差异在这里收敛。

    DashScope 兼容模式需在 base 后追加 /compatible-mode/v1 才能用 ChatOpenAI 协议。
    OpenAI 兼容模式假定 base_url 已带版本路径，由管理员在前台填正确。
    """
    base = base_url.rstrip("/")
    if adapter == AdapterType.DASHSCOPE:
        return f"{base}{_COMPAT_PATH}"
    return base


def _build_image_provider(
    adapter: AdapterType,
    image_cv: ModelConnectionVersion,
    generate_model_id: str,
    edit_model_id: str | None,
) -> ImageProvider:
    """按 adapter 类型分派到具体 provider。编辑模型留空则复用生成模型名。"""
    edit_model = edit_model_id or generate_model_id
    if adapter == AdapterType.MOCK:
        return MockImageProvider()
    if adapter == AdapterType.DASHSCOPE:
        return DashScopeImageProvider(
            base_url=image_cv.base_url,
            api_key=_decrypt_key(image_cv),
            text_to_image_model=generate_model_id,
            image_edit_model=edit_model,
        )
    if adapter == AdapterType.OPENAI_IMAGE:
        return OpenAIImageProvider(
            base_url=image_cv.base_url,
            api_key=_decrypt_key(image_cv),
            model=generate_model_id,
            edit_model=edit_model,
        )
    raise IncompatibleRuntime(f"不支持的图像 adapter：{adapter}")


def _decrypt_key(version: ModelConnectionVersion) -> str:
    try:
        return decrypt_secret(version.encrypted_api_key)
    except DecryptionFailed as exc:
        raise IncompatibleRuntime("连接密钥不可读") from exc