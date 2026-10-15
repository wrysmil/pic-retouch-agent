"""provider 调用的辅助函数。

把"按任务绑定版本拿图像客户端"这件事收敛到这里，
后续工具文件只管业务，不必重复解析版本。
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tool_run import ToolRun
from app.providers.base import ImageProvider
from app.services.model_runtime import (
    ImageClient,
    IncompatibleRuntime,
    RuntimeMissing,
    get_image_client,
)


class ProviderNotBound(Exception):
    """任务没有绑定模型配置版本。"""


async def image_client_for_run(session: AsyncSession, run: ToolRun) -> ImageClient:
    """按任务的运行时版本取得图像客户端。任务未绑定版本时抛 ProviderNotBound。"""
    if run.runtime_config_version_id is None:
        raise ProviderNotBound("任务未绑定模型配置版本，请重新发起")
    return await get_image_client(session, run.runtime_config_version_id)


async def provider_for_run(session: AsyncSession, run: ToolRun) -> ImageProvider:
    """便捷封装：直接拿到 provider，隐藏 ImageClient 包装。"""
    return (await image_client_for_run(session, run)).provider


def unwrap_runtime_error(exc: Exception) -> Exception:
    """把版本解析异常转成可向用户展示的 ProviderError。"""
    if isinstance(exc, (RuntimeMissing, IncompatibleRuntime, ProviderNotBound)):
        from app.providers.base import ProviderError

        return ProviderError(str(exc))
    return exc