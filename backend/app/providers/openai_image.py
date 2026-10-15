"""OpenAI Images API 适配器（gpt-image-* 系列）。

按 OpenAI 官方 v1/images 文档实现：
- 文生图走 POST /v1/images/generations
- 图像编辑走 POST /v1/images/edits（multipart/form-data：image + prompt）

不同厂商可能只部分实现这套接口；管理员在保存模型前应自行验证。
"""

import base64
import io

import httpx

from app.providers.base import (
    EditRequest,
    GenerateRequest,
    ImageProvider,
    ProgressCallback,
    ProviderError,
)


class OpenAIImageProvider(ImageProvider):
    name = "openai_image"

    def __init__(self, base_url: str, api_key: str, model: str, edit_model: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._edit_model = edit_model
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._client = httpx.AsyncClient(
            base_url=self._base_url, headers=self._headers, timeout=60.0
        )

    async def generate(
        self, request: GenerateRequest, on_progress: ProgressCallback | None = None
    ) -> list[bytes]:
        payload: dict = {
            "model": self._model,
            "prompt": request.prompt,
            "n": request.count,
            "size": f"{request.width}x{request.height}",
        }
        if request.negative_prompt:
            # OpenAI 原生接口不识别 negative prompt；保留以便后续扩展
            payload["negative_prompt"] = request.negative_prompt

        try:
            response = await self._client.post("/images/generations", json=payload)
            response.raise_for_status()
            body = response.json()
        except httpx.HTTPError as exc:
            raise ProviderError(f"OpenAI 图像接口调用失败：{exc}") from exc

        items = body.get("data") or []
        if not items:
            raise ProviderError("OpenAI 图像接口未返回 data")
        return [_decode(item) for item in items]

    async def edit(
        self, request: EditRequest, on_progress: ProgressCallback | None = None
    ) -> list[bytes]:
        files = {
            "image": ("image.png", request.image, "image/png"),
            # OpenAI Edit 必填 prompt
            "prompt": (None, request.prompt),
        }
        data: dict = {"model": self._edit_model, "n": str(request.count)}
        if request.width and request.height:
            data["size"] = f"{request.width}x{request.height}"

        try:
            response = await self._client.post(
                "/images/edits", data=data, files=files
            )
            response.raise_for_status()
            body = response.json()
        except httpx.HTTPError as exc:
            raise ProviderError(f"OpenAI 图像编辑接口调用失败：{exc}") from exc

        items = body.get("data") or []
        if not items:
            raise ProviderError("OpenAI 图像编辑接口未返回 data")
        return [_decode(item) for item in items]

    async def upscale(self, image: bytes, scale: int, on_progress: ProgressCallback | None = None) -> bytes:
        # OpenAI 没有专门的 upscale 接口；通过 edit 把分辨率拉高
        from PIL import Image

        source = Image.open(io.BytesIO(image))
        width, height = source.width * scale, source.height * scale
        results = await self.edit(
            EditRequest(
                prompt="提高清晰度，保持构图不变",
                image=image,
                width=width,
                height=height,
            ),
            on_progress,
        )
        return results[0]


def _decode(item: dict) -> bytes:
    """OpenAI 返回 base64 字符串或 url；统一取回二进制。"""
    if "b64_json" in item and item["b64_json"]:
        return base64.b64decode(item["b64_json"])
    if "url" in item and item["url"]:
        # 编辑接口一般返回 url。下载留作备用，避免本地服务被厂商地址策略拒掉时整轮失败
        import httpx

        try:
            response = httpx.get(item["url"], timeout=60.0)
            response.raise_for_status()
            return response.content
        except httpx.HTTPError as exc:
            raise ProviderError(f"OpenAI 返回的图片下载失败：{exc}") from exc
    raise ProviderError("OpenAI 图像接口返回的 item 缺少 b64_json 或 url")