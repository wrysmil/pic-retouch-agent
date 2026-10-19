"""Toookens 图像适配器（qwen-image-* 等）。

按 Toookens API 手册的「图像系列」实现：
- 提交一律走 ``POST /images/generations``，鉴权用 ``Authorization: Bearer <key>``。
- 同步模型直接返回图片字段；异步模型返回 202 + ``task_id`` / ``task_query_url``，
  按 ``poll_after_seconds`` 轮询 ``GET /images/tasks/{task_id}`` 到终态。
- 用 ``operation_mode`` 区分文生图 / 图生图 / 多参考图，而不是换端点。

与 OpenAI Images 协议的关键差异（因此单列一个 adapter）：
1. 没有独立的编辑端点，图生图靠 ``operation_mode=image_to_image`` + ``image``。
2. 参考图以 data URL 内联即可（已实测上游接受），不要求公网可达地址，
   本地对象存储的签名 URL 因此不必暴露到公网。
3. 尺寸受模型能力约束：``supports_custom_size=false`` 的模型（如 qwen-image-2.0）
   只认 ``supported_sizes``，超出的请求必须收敛，否则上游返回 ``invalid_image_size``。
   能力通过 ModelDefinition.param_schema 声明，见 ``_Capabilities.from_schema``。
"""

import asyncio
import base64
import io

import httpx
from PIL import Image

from app.providers.base import (
    EditRequest,
    GenerateRequest,
    ImageProvider,
    ProgressCallback,
    ProviderError,
)

_SUBMIT_PATH = "/images/generations"
_TASK_PATH = "/images/tasks/{task_id}"

_SUBMIT_TIMEOUT = 120.0
_DOWNLOAD_TIMEOUT = 60.0
_POLL_TIMEOUT = 420.0
_DEFAULT_POLL_INTERVAL = 3.0
_MAX_POLL_INTERVAL = 15.0

_TERMINAL_OK = "succeeded"
_TERMINAL_BAD = {"failed", "cancelled", "canceled"}

_OP_TEXT = "text_to_image"
_OP_IMAGE = "image_to_image"
_OP_MULTI = "multi_reference_image"


class _Capabilities:
    """从 param_schema 解析出的模型尺寸与操作模式能力。

    schema 全空时按“不限制”处理：直接把请求尺寸透传给上游，保持与其它
    adapter 一致的行为；需要严格约束的模型在登记时写明能力即可。
    """

    __slots__ = (
        "default_size",
        "supported_sizes",
        "supports_custom_size",
        "min_pixels",
        "max_pixels",
        "aspect_min",
        "aspect_max",
        "supports_image_to_image",
        "supports_multi_reference",
    )

    def __init__(self, schema: dict | None) -> None:
        schema = schema or {}
        sizes = schema.get("supported_sizes") or []
        self.supported_sizes: tuple[str, ...] = tuple(
            str(item) for item in sizes if _parse_size(str(item))
        )
        declared_default = str(schema.get("default_size") or "").strip()
        # default_size 可能是 "auto" / "1K" 这类预设，不是像素尺寸时退回首个固定尺寸
        self.default_size: str | None = (
            declared_default
            if _parse_size(declared_default)
            else (self.supported_sizes[0] if self.supported_sizes else None)
        )

        custom = schema.get("supports_custom_size")
        if custom is None:
            # 没声明自定义能力时，以“是否给了固定尺寸”推断：给了就只能在其中选
            self.supports_custom_size = not self.supported_sizes
        else:
            self.supports_custom_size = bool(custom)

        constraints = schema.get("custom_size_constraints") or {}
        self.min_pixels: int | None = _as_int(constraints.get("minimum_pixels"))
        self.max_pixels: int | None = _as_int(constraints.get("maximum_pixels"))
        self.aspect_min: float | None = _as_float(constraints.get("aspect_ratio_min"))
        self.aspect_max: float | None = _as_float(constraints.get("aspect_ratio_max"))

        modes = {str(item) for item in (schema.get("supported_operation_modes") or [])}
        self.supports_image_to_image = not modes or _OP_IMAGE in modes
        self.supports_multi_reference = _OP_MULTI in modes or bool(
            schema.get("supports_multi_reference_image")
        )

    def resolve_size(self, width: int, height: int) -> str:
        """把请求尺寸收敛成上游一定接受的 size 字符串。"""
        requested = f"{width}x{height}"
        if requested in self.supported_sizes:
            return requested

        if self.supports_custom_size and self._within_constraints(width, height):
            return requested

        if not self.supports_custom_size:
            # 固定尺寸模型：取同比例里最接近的一张，没有同比例就退回默认尺寸
            return self._nearest(width, height)

        # 允许自定义但不满足像素/比例约束：按比例裁到最近的合法像素量
        return self._clamp(width, height)

    def _within_constraints(self, width: int, height: int) -> bool:
        pixels = width * height
        if self.min_pixels is not None and pixels < self.min_pixels:
            return False
        if self.max_pixels is not None and pixels > self.max_pixels:
            return False
        if width <= 0 or height <= 0:
            return False
        ratio = width / height
        if self.aspect_min is not None and ratio < self.aspect_min:
            return False
        if self.aspect_max is not None and ratio > self.aspect_max:
            return False
        return True

    def _nearest(self, width: int, height: int) -> str:
        if not self.supported_sizes:
            return self.default_size or f"{width}x{height}"
        target = width / height

        def score(size: str) -> tuple[float, int]:
            parsed = _parse_size(size)
            if parsed is None:
                return (float("inf"), 0)
            w, h = parsed
            ratio_gap = abs(w / h - target)
            pixel_gap = abs(w * h - width * height)
            return (ratio_gap, pixel_gap)

        return min(self.supported_sizes, key=score)

    def _clamp(self, width: int, height: int) -> str:
        ratio = width / height if height else 1.0
        if self.aspect_min is not None:
            ratio = max(ratio, self.aspect_min)
        if self.aspect_max is not None:
            ratio = min(ratio, self.aspect_max)

        pixels = width * height
        if self.min_pixels is not None:
            pixels = max(pixels, self.min_pixels)
        if self.max_pixels is not None:
            pixels = min(pixels, self.max_pixels)

        height_out = max(1, int(round((pixels / ratio) ** 0.5)))
        width_out = max(1, int(round(height_out * ratio)))
        return f"{width_out}x{height_out}"


class ToookensImageProvider(ImageProvider):
    """Toookens 统一图像接口；同步与异步任务都归一到「返回图片字节」。"""

    name = "toookens"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        edit_model: str | None = None,
        param_schema: dict | None = None,
        client: httpx.AsyncClient | None = None,
        download_client: httpx.AsyncClient | None = None,
    ) -> None:
        """由 model_runtime 按发布的连接版本注入参数，不读环境变量。

        client / download_client 只用于测试注入；生产路径下前者由本类创建并带鉴权头，
        后者懒加载且不带任何鉴权头——结果链接常指向厂商 CDN，不能把 API Key 带过去。
        """
        if not api_key:
            raise ProviderError("Toookens 连接未配置 API Key")
        self._model = model
        self._edit_model = edit_model or model
        self._caps = _Capabilities(param_schema)
        # 鉴权头在每次请求上显式携带，而不是只挂在自建 client 上，
        # 这样注入 client 的场景（测试）与生产走的是同一条鉴权路径。
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._client = client or httpx.AsyncClient(
            base_url=base_url.rstrip("/"), timeout=_SUBMIT_TIMEOUT
        )
        self._downloads = download_client

    async def aclose(self) -> None:
        await self._client.aclose()
        if self._downloads is not None:
            await self._downloads.aclose()

    async def generate(
        self, request: GenerateRequest, on_progress: ProgressCallback | None = None
    ) -> list[bytes]:
        return await self._invoke(self._generate_payload(request), on_progress)

    async def edit(
        self, request: EditRequest, on_progress: ProgressCallback | None = None
    ) -> list[bytes]:
        payload: dict = {
            "model": self._edit_model,
            "prompt": request.prompt,
            "n": max(1, request.count),
            "response_format": "url",
            "operation_mode": _OP_IMAGE,
            "image": _to_data_url(request.image),
        }
        if request.width and request.height:
            payload["size"] = self._caps.resolve_size(request.width, request.height)
        if request.negative_prompt:
            payload["negative_prompt"] = request.negative_prompt
        return await self._invoke(payload, on_progress)

    async def upscale(
        self, image: bytes, scale: int, on_progress: ProgressCallback | None = None
    ) -> bytes:
        source = Image.open(io.BytesIO(image))
        results = await self.edit(
            EditRequest(
                prompt="提高清晰度，保持主体、构图和颜色不变，不要添加新元素。",
                image=image,
                width=source.width * max(1, scale),
                height=source.height * max(1, scale),
            ),
            on_progress,
        )
        return results[0]

    # ---- 请求构造 ----

    def _generate_payload(self, request: GenerateRequest) -> dict:
        """按参考图数量选择操作模式，并把图片内联成 data URL。"""
        payload: dict = {
            "model": self._model,
            "prompt": request.prompt,
            "n": max(1, request.count),
            "response_format": "url",
        }
        references = request.references

        if not references:
            payload["operation_mode"] = _OP_TEXT
        elif len(references) > 1 and self._caps.supports_multi_reference:
            payload["operation_mode"] = _OP_MULTI
            payload["reference_images"] = [_to_data_url(raw) for raw in references]
        else:
            # 只支持单参考图的模型：多图时取第一张，避免整轮失败
            payload["operation_mode"] = _OP_IMAGE
            payload["image"] = _to_data_url(references[0])

        payload["size"] = self._caps.resolve_size(request.width, request.height)
        if request.negative_prompt:
            payload["negative_prompt"] = request.negative_prompt
        return payload

    # ---- 调用与结果解析 ----

    async def _invoke(
        self, payload: dict, on_progress: ProgressCallback | None
    ) -> list[bytes]:
        body = await self._submit(payload)

        images = _extract_images(body)
        if images:
            if on_progress:
                await on_progress(80, "下载结果")
            return await self._fetch_all(images)

        task_id = body.get("task_id")
        if not task_id:
            message = _error_text(body) or "图像接口未返回图片或任务 ID"
            raise ProviderError(f"Toookens 生图失败：{message}")

        if on_progress:
            await on_progress(10, "排队中")
        result = await self._poll(str(task_id), body, on_progress)

        images = _extract_images(result)
        if not images:
            raise ProviderError("Toookens 任务成功但未返回图片")
        if on_progress:
            await on_progress(80, "下载结果")
        return await self._fetch_all(images)

    async def _fetch_all(self, items: list[tuple[str, str]]) -> list[bytes]:
        """并发取回图片；b64 直接解码，URL 走一次下载（结果链接会过期，须立即转存）。"""
        return list(
            await asyncio.gather(
                *(
                    _decode_b64(payload) if kind == "b64" else self._download(payload)
                    for kind, payload in items
                )
            )
        )

    async def _download(self, url: str) -> bytes:
        if self._downloads is None:
            self._downloads = httpx.AsyncClient(timeout=_DOWNLOAD_TIMEOUT)
        try:
            response = await self._downloads.get(url)
        except httpx.HTTPError as exc:
            raise ProviderError(f"生成结果下载失败：{exc}") from exc
        if response.status_code != httpx.codes.OK:
            raise ProviderError(f"生成结果下载失败（HTTP {response.status_code}）")
        return response.content

    async def _submit(self, payload: dict) -> dict:
        # model 放在 payload 里一起提交，便于日志里对齐
        try:
            response = await self._client.post(_SUBMIT_PATH, json=payload, headers=self._headers)
        except httpx.HTTPError as exc:
            raise ProviderError(f"Toookens 生图请求失败：{exc}") from exc
        return _parse(response, "生图")

    async def _poll(
        self, task_id: str, submitted: dict, on_progress: ProgressCallback | None
    ) -> dict:
        interval = _as_float(submitted.get("poll_after_seconds")) or _DEFAULT_POLL_INTERVAL
        loop = asyncio.get_running_loop()
        deadline = loop.time() + _POLL_TIMEOUT
        started = loop.time()

        while True:
            await asyncio.sleep(min(max(interval, 1.0), _MAX_POLL_INTERVAL))
            try:
                response = await self._client.get(
                    _TASK_PATH.format(task_id=task_id), headers=self._headers
                )
            except httpx.HTTPError as exc:
                raise ProviderError(f"Toookens 任务查询失败：{exc}") from exc

            body = _parse(response, "任务查询")
            status = str(body.get("status") or body.get("task_status") or "").lower()

            if status == _TERMINAL_OK:
                return body
            if status in _TERMINAL_BAD:
                message = _error_text(body) or "上游未说明原因"
                raise ProviderError(f"Toookens 生成任务{status}：{message}")

            if on_progress and status:
                waited = loop.time() - started
                stage = "排队中" if status in ("queued", "pending", "dispatching") else "生成中"
                await on_progress(min(78, 12 + int(waited / 2.5)), stage)

            if loop.time() > deadline:
                raise ProviderError("Toookens 生成任务超时")
            # 未给 poll_after_seconds 时逐步退避，降低轮询压力
            interval = min(interval * 1.5, _MAX_POLL_INTERVAL)


async def _decode_b64(payload: str) -> bytes:
    try:
        return base64.b64decode(payload)
    except (ValueError, TypeError) as exc:
        raise ProviderError("图片 base64 解码失败") from exc


def _extract_images(body: dict) -> list[tuple[str, str]]:
    """从同步响应或任务详情里取出图片，返回 (来源, 载荷) 列表。"""
    found: list[tuple[str, str]] = []

    output = body.get("output")
    if isinstance(output, dict):
        for url in output.get("image_urls") or []:
            if url:
                found.append(("url", str(url)))

    for item in body.get("data") or []:
        if not isinstance(item, dict):
            continue
        if item.get("b64_json"):
            found.append(("b64", str(item["b64_json"])))
        elif item.get("url"):
            found.append(("url", str(item["url"])))

    return found


def _parse(response: httpx.Response, action: str) -> dict:
    try:
        body = response.json()
    except ValueError as exc:
        raise ProviderError(
            f"Toookens {action}返回非 JSON 响应（HTTP {response.status_code}）"
        ) from exc

    if not isinstance(body, dict):
        raise ProviderError(f"Toookens {action}返回结构异常")

    ok = response.status_code < httpx.codes.BAD_REQUEST
    if not ok or _error_text(body):
        message = _error_text(body) or f"HTTP {response.status_code}"
        raise ProviderError(f"Toookens {action}失败：{message}")
    return body


def _error_text(body: dict) -> str:
    """兼容不同错误字段形态，拼出可读信息。"""
    for key in ("error_message", "detail", "message"):
        value = body.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            inner = value.get("message") or value.get("detail")
            if isinstance(inner, str) and inner.strip():
                return inner.strip()

    code = body.get("error_code")
    if isinstance(code, str) and code.strip():
        return code.strip()

    error = body.get("error")
    if isinstance(error, str) and error.strip():
        return error.strip()
    if isinstance(error, dict):
        inner = error.get("message")
        if isinstance(inner, str) and inner.strip():
            return inner.strip()
    return ""


def _to_data_url(raw: bytes) -> str:
    return f"data:{_sniff_mime(raw)};base64,{base64.b64encode(raw).decode()}"


def _sniff_mime(raw: bytes) -> str:
    """按魔数判断图片类型，避免把 JPEG 标成 PNG 后上游解析失败。"""
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if raw[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"


def _parse_size(value: str) -> tuple[int, int] | None:
    text = value.strip().lower().replace("*", "x")
    if "x" not in text:
        return None
    left, _, right = text.partition("x")
    try:
        width, height = int(left), int(right)
    except ValueError:
        return None
    if width <= 0 or height <= 0:
        return None
    return width, height


def _as_int(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _as_float(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
