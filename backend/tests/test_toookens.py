"""Toookens 适配器的离线测试。

全部走 httpx.MockTransport，不发任何真实请求，也不产生调用费用。
真实接口的关键行为（202 异步任务、data URL 参考图、自定义尺寸）已在接入时实测确认，
这里固化成回归用例，避免后续改动破坏协议细节。
"""

import base64
import io
import json

import httpx
import pytest
from PIL import Image

from app.providers.base import EditRequest, GenerateRequest, ProviderError
from app.providers.toookens import ToookensImageProvider

_SUBMIT_URL = "https://api.toookens.com/v1/images/generations"

# 与后台登记时写入 param_schema 的能力描述保持一致
_QWEN_3_CAPS = {
    "default_size": "auto",
    "supported_sizes": ["1024x1024", "1536x1024", "1024x1536", "2048x2048"],
    "supports_custom_size": True,
    "custom_size_constraints": {
        "minimum_pixels": 262144,
        "maximum_pixels": 4194304,
        "aspect_ratio_min": 0.125,
        "aspect_ratio_max": 8.0,
    },
    "supported_operation_modes": ["text_to_image", "image_to_image", "multi_reference_image"],
    "supports_multi_reference_image": True,
}

_QWEN_2_CAPS = {
    "default_size": "1024x1024",
    "supported_sizes": ["1024x1024"],
    "supports_custom_size": False,
    "supported_operation_modes": ["text_to_image", "image_to_image"],
}


def _png(color: tuple[int, int, int] = (10, 120, 200), size: tuple[int, int] = (64, 64)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def _provider(handler, caps: dict | None = None, **kwargs) -> ToookensImageProvider:
    """把提交与结果下载都接到同一个 MockTransport 上。"""
    transport = httpx.MockTransport(handler)
    return ToookensImageProvider(
        base_url="https://api.toookens.com/v1",
        api_key="test-key",
        model="qwen-image-3.0",
        param_schema=caps if caps is not None else _QWEN_3_CAPS,
        client=httpx.AsyncClient(
            transport=transport, base_url="https://api.toookens.com/v1"
        ),
        download_client=httpx.AsyncClient(transport=transport),
        **kwargs,
    )


def _sync_response(_: httpx.Request) -> httpx.Response:
    payload = base64.b64encode(_png()).decode()
    return httpx.Response(200, json={"data": [{"b64_json": payload}]})


def _record(seen: list[httpx.Request], inner):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return inner(request)

    return handler


async def test_text_to_image_sync_b64() -> None:
    seen: list[httpx.Request] = []
    provider = _provider(_record(seen, _sync_response))

    images = await provider.generate(
        GenerateRequest(prompt="一只猫", width=1080, height=1350, count=1)
    )

    assert len(images) == 1
    assert images[0][:8] == b"\x89PNG\r\n\x1a\n"

    body = json.loads(seen[0].content)
    assert body["model"] == "qwen-image-3.0"
    assert body["operation_mode"] == "text_to_image"
    # 1080x1350 在自定义尺寸约束内，应按原比例透传而不是被压成正方形
    assert body["size"] == "1080x1350"
    assert body["response_format"] == "url"
    assert seen[0].headers["authorization"] == "Bearer test-key"


async def test_async_task_is_polled_until_succeeded() -> None:
    """202 + task_id 时必须轮询任务接口，并从 output.image_urls 取图。"""
    seen: list[httpx.Request] = []
    png = _png()
    polls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path.endswith("/images/generations"):
            return httpx.Response(
                202,
                json={
                    "task_id": "t-1",
                    "status": "queued",
                    "poll_after_seconds": 1,
                    "task_query_url": "https://api.toookens.com/v1/images/tasks/t-1",
                },
            )
        if request.url.path.endswith("/images/tasks/t-1"):
            polls["n"] += 1
            if polls["n"] < 2:
                return httpx.Response(200, json={"task_id": "t-1", "status": "running"})
            return httpx.Response(
                200,
                json={
                    "task_id": "t-1",
                    "status": "succeeded",
                    "output": {"image_urls": ["https://cdn.example.com/a.png"], "image_count": 1},
                },
            )
        # 结果下载
        return httpx.Response(200, content=png)

    provider = _provider(handler)
    images = await provider.generate(
        GenerateRequest(prompt="一只猫", width=1024, height=1024, count=1)
    )

    assert images == [png]
    assert polls["n"] == 2
    task_calls = [r for r in seen if "/images/tasks/" in r.url.path]
    assert task_calls and task_calls[0].headers["authorization"] == "Bearer test-key"
    # 结果 CDN 请求不得携带 API Key
    download_calls = [r for r in seen if r.url.host == "cdn.example.com"]
    assert download_calls and "authorization" not in download_calls[0].headers


async def test_single_reference_uses_image_to_image_with_data_url() -> None:
    seen: list[httpx.Request] = []
    provider = _provider(_record(seen, _sync_response))

    await provider.generate(
        GenerateRequest(prompt="换背景", width=1024, height=1024, references=[_png()])
    )

    body = json.loads(seen[0].content)
    assert body["operation_mode"] == "image_to_image"
    assert body["image"].startswith("data:image/png;base64,")
    assert "reference_images" not in body


async def test_multiple_references_use_multi_reference_mode() -> None:
    seen: list[httpx.Request] = []
    provider = _provider(_record(seen, _sync_response))

    await provider.generate(
        GenerateRequest(
            prompt="融合", width=1024, height=1024, references=[_png(), _png((200, 30, 30))]
        )
    )

    body = json.loads(seen[0].content)
    assert body["operation_mode"] == "multi_reference_image"
    assert len(body["reference_images"]) == 2
    assert all(url.startswith("data:image/png;base64,") for url in body["reference_images"])


async def test_multi_reference_degrades_when_unsupported() -> None:
    """qwen-image-2.0 不支持多参考图：退化用第一张，而不是让整轮失败。"""
    seen: list[httpx.Request] = []
    provider = _provider(_record(seen, _sync_response), caps=_QWEN_2_CAPS)

    await provider.generate(
        GenerateRequest(prompt="融合", width=1024, height=1024, references=[_png(), _png()])
    )

    body = json.loads(seen[0].content)
    assert body["operation_mode"] == "image_to_image"
    assert "reference_images" not in body


async def test_fixed_size_model_coerces_unsupported_size() -> None:
    """固定尺寸模型只能收到 supported_sizes 里的值，否则上游报 invalid_image_size。"""
    seen: list[httpx.Request] = []
    provider = _provider(_record(seen, _sync_response), caps=_QWEN_2_CAPS)

    await provider.generate(GenerateRequest(prompt="一只猫", width=1080, height=1920, count=1))

    assert json.loads(seen[0].content)["size"] == "1024x1024"


async def test_custom_size_is_clamped_into_pixel_bounds() -> None:
    """超出像素上限的请求按比例收敛，而不是原样透传被上游拒绝。"""
    seen: list[httpx.Request] = []
    provider = _provider(_record(seen, _sync_response))

    await provider.generate(GenerateRequest(prompt="一只猫", width=4096, height=4096, count=1))

    size = json.loads(seen[0].content)["size"]
    width, height = (int(part) for part in size.split("x"))
    assert 262144 <= width * height <= 4194304
    # 比例保持 1:1
    assert width == height


async def test_edit_sends_image_to_image() -> None:
    seen: list[httpx.Request] = []
    provider = _provider(_record(seen, _sync_response))

    images = await provider.edit(
        EditRequest(prompt="只改背景", image=_png(), width=1024, height=1536)
    )

    assert len(images) == 1
    body = json.loads(seen[0].content)
    assert body["operation_mode"] == "image_to_image"
    assert body["size"] == "1024x1536"
    assert body["model"] == "qwen-image-3.0"


async def test_edit_without_size_omits_field() -> None:
    """region/layers 等工具不传画幅，此时应交给上游默认，而不是硬塞一个尺寸。"""
    seen: list[httpx.Request] = []
    provider = _provider(_record(seen, _sync_response))

    await provider.edit(EditRequest(prompt="只改背景", image=_png()))

    assert "size" not in json.loads(seen[0].content)


async def test_failed_task_raises_with_reason() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/images/generations"):
            return httpx.Response(202, json={"task_id": "t-2", "status": "queued"})
        return httpx.Response(
            200,
            json={"task_id": "t-2", "status": "failed", "error_message": "内容审核未通过"},
        )

    provider = _provider(handler)
    with pytest.raises(ProviderError, match="内容审核未通过"):
        await provider.generate(GenerateRequest(prompt="x", width=1024, height=1024))


async def test_submit_error_surfaces_message() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400, json={"error_code": "invalid_image_size", "error_message": "尺寸不支持"}
        )

    provider = _provider(handler)
    with pytest.raises(ProviderError, match="尺寸不支持"):
        await provider.generate(GenerateRequest(prompt="x", width=1024, height=1024))


async def test_non_json_response_is_reported() -> None:
    provider = _provider(lambda _: httpx.Response(502, text="<html>bad gateway</html>"))

    with pytest.raises(ProviderError, match="非 JSON"):
        await provider.generate(GenerateRequest(prompt="x", width=1024, height=1024))


async def test_sync_url_response_is_downloaded() -> None:
    """同步 200 + data[].url 也应直接取图，不强制轮询。"""
    seen: list[httpx.Request] = []
    png = _png()

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.host == "cdn.example.com":
            return httpx.Response(200, content=png)
        return httpx.Response(200, json={"data": [{"url": "https://cdn.example.com/b.png"}]})

    provider = _provider(handler)
    images = await provider.generate(GenerateRequest(prompt="x", width=1024, height=1024))

    assert images == [png]
    assert not any("/images/tasks/" in r.url.path for r in seen)


async def test_missing_api_key_is_rejected() -> None:
    with pytest.raises(ProviderError, match="API Key"):
        ToookensImageProvider(
            base_url="https://api.toookens.com/v1", api_key="", model="qwen-image-3.0"
        )
