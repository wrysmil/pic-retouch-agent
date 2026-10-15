"""Provider 工厂入口。

运行时代码统一通过 services.model_runtime.get_image_client 取得客户端，
按后台发布的运行版本解析连接与模型，不再从环境变量构造 provider。
本模块只导出适配器基类与 Mock 实现。
"""

from app.providers.base import EditRequest, GenerateRequest, ImageProvider, ProviderError
from app.providers.mock import MockImageProvider

__all__ = [
    "EditRequest",
    "GenerateRequest",
    "ImageProvider",
    "MockImageProvider",
    "ProviderError",
]