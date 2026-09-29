"""连通性自检：基础设施、图像 provider、规划模型、抠图 provider 各跑一次最小调用。

只发最小请求：图像 1 张 512×512，规划 1 条短指令。真实调用会产生费用，
未配置 key 的项报 SKIP 而不是 FAIL，因为那是预期状态而非故障。

    python scripts/check_providers.py
"""

import asyncio
import io
import sys
from pathlib import Path

# 直接以脚本方式运行时，app 包不在导入路径上
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain_core.messages import HumanMessage
from sqlalchemy import text

from app.agent.llm import PlannerUnavailable, planner
from app.config import get_settings
from app.edits.pixels import remove_background
from app.providers import GenerateRequest, ProviderError, get_image_provider

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"

_results: list[tuple[str, str, str]] = []


def _record(status: str, name: str, detail: str) -> None:
    _results.append((status, name, detail))
    print(f"[{status}] {name:<12} {detail}")


async def check_storage() -> None:
    """API 用到的三样外部依赖，逐个打一次真实连接。"""

    from app import storage
    from app.db import SessionFactory

    try:
        async with SessionFactory() as session:
            await session.execute(text("SELECT 1"))
        _record(PASS, "postgres", "可连接")
    except Exception as exc:
        _record(FAIL, "postgres", f"{type(exc).__name__}: {exc}")

    try:
        import redis.asyncio as redis

        client = redis.from_url(get_settings().redis_url)
        await client.ping()
        await client.aclose()
        _record(PASS, "redis", "可连接")
    except Exception as exc:
        _record(FAIL, "redis", f"{type(exc).__name__}: {exc}")

    try:
        key = "check/providers"
        await storage.put(key, b"ok", "text/plain")
        await storage.get(key)
        await storage.delete(key)
        _record(PASS, "minio", "可读写")
    except Exception as exc:
        _record(FAIL, "minio", f"{type(exc).__name__}: {exc}")


async def check_image_provider() -> None:
    """按 IMAGE_PROVIDER 发一次真实出图请求；未配置 key 时报 SKIP。"""

    settings = get_settings()
    if settings.image_provider == "dashscope" and not settings.dashscope_api_key:
        _record(SKIP, "image", "IMAGE_PROVIDER=dashscope 但未配置 DASHSCOPE_API_KEY")
        return

    try:
        provider = get_image_provider()
        images = await provider.generate(GenerateRequest(prompt="一朵云", width=512, height=512))
        size = len(images[0]) if images else 0
        _record(PASS if images else FAIL, "image", f"provider={provider.name} 返回 {len(images)} 张，首张 {size} 字节")
    except ProviderError as exc:
        _record(FAIL, "image", f"ProviderError: {exc}")
    except Exception as exc:
        _record(FAIL, "image", f"{type(exc).__name__}: {exc}")


async def check_planner() -> None:
    """真实调一次规划模型，确认 key 有效且账号开通了 Function Calling。"""

    settings = get_settings()
    if not settings.dashscope_api_key:
        _record(SKIP, "planner", "未配置 DASHSCOPE_API_KEY")
        return

    try:
        model = planner()
        reply = await model.ainvoke([HumanMessage("只回复：就绪")])
        calls = getattr(reply, "tool_calls", [])
        _record(
            PASS,
            "planner",
            f"model={settings.planner_model} 回复「{reply.content}」tool_calls={len(calls)}",
        )
    except PlannerUnavailable as exc:
        _record(FAIL, "planner", f"PlannerUnavailable: {exc}")
    except Exception as exc:
        _record(FAIL, "planner", f"{type(exc).__name__}: {exc}")


def check_matting() -> None:
    """抠图是本地计算，但要确认 rembg 可用；首次调用会下载模型。"""

    settings = get_settings()
    try:
        from PIL import Image

        buffer = io.BytesIO()
        Image.new("RGB", (64, 64), (200, 200, 200)).save(buffer, format="PNG")
        output = remove_background(buffer.getvalue())
        has_alpha = Image.open(io.BytesIO(output)).mode == "RGBA"
        _record(PASS, "matting", f"provider={settings.matting_provider} 输出含透明通道={has_alpha}")
    except Exception as exc:
        _record(FAIL, "matting", f"{type(exc).__name__}: {exc}")


async def main() -> int:
    settings = get_settings()
    print(
        f"配置：IMAGE_PROVIDER={settings.image_provider} "
        f"TEXT_TO_IMAGE_MODEL={settings.text_to_image_model} "
        f"PLANNER_MODEL={settings.planner_model}\n"
    )

    await check_storage()
    await check_image_provider()
    await check_planner()
    check_matting()

    failed = [name for status, name, _ in _results if status == FAIL]
    skipped = [name for status, name, _ in _results if status == SKIP]
    print()
    print(f"合计 {len(_results)} 项：失败 {len(failed)}，跳过 {len(skipped)}")
    if failed:
        print("失败项：" + "、".join(failed))
    if skipped:
        print("跳过项（未配置）：" + "、".join(skipped))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
