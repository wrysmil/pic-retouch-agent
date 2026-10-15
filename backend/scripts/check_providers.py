"""连通性自检：基础设施、图像模型、规划模型、抠图各跑一次最小调用。

AI 模型（规划 / 文生图 / 图编辑）一律走后台「模型配置」发布的运行版本，
经 services.model_runtime 解析，不再读环境变量。尚未发布运行版本时报 SKIP，
因为那是预期状态而非故障。真实调用会产生费用，只发最小请求。

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

from app.agent.llm import bind_tools
from app.config import get_settings
from app.db import SessionFactory
from app.edits.pixels import remove_background
from app.providers import GenerateRequest, ProviderError
from app.services import model_config
from app.services.model_runtime import (
    IncompatibleRuntime,
    RuntimeMissing,
    get_image_client,
    get_planner,
)

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"

_results: list[tuple[str, str, str]] = []


def _record(status: str, name: str, detail: str) -> None:
    _results.append((status, name, detail))
    print(f"[{status}] {name:<12} {detail}")


async def check_storage() -> None:
    """API 用到的三样外部依赖，逐个打一次真实连接。"""

    from app import storage

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


async def check_runtime() -> None:
    """按后台发布的当前运行版本，各调一次规划模型与文生图。"""
    async with SessionFactory() as session:
        version = await model_config.get_current_version(session)
        if version is None:
            _record(SKIP, "runtime", "尚未在后台发布运行配置，请先在「模型配置」中发布")
            return

        _record(PASS, "runtime", f"当前运行版本 v{version.version_seq}")

        # 规划模型
        try:
            planner = await get_planner(session, version.id)
            reply = await bind_tools(planner.client).ainvoke([HumanMessage("只回复：就绪")])
            calls = getattr(reply, "tool_calls", [])
            _record(PASS, "planner", f"model={planner.model_definition.vendor_model_id} 回复「{reply.content}」tool_calls={len(calls)}")
        except (RuntimeMissing, IncompatibleRuntime) as exc:
            _record(FAIL, "planner", f"{type(exc).__name__}: {exc}")
        except Exception as exc:
            _record(FAIL, "planner", f"{type(exc).__name__}: {exc}")

        # 文生图
        try:
            image = await get_image_client(session, version.id)
            images = await image.provider.generate(
                GenerateRequest(prompt="一朵云", width=512, height=512, count=1)
            )
            size = len(images[0]) if images else 0
            _record(
                PASS if images else FAIL,
                "image",
                f"provider={image.provider.name} 返回 {len(images)} 张，首张 {size} 字节",
            )
        except ProviderError as exc:
            _record(FAIL, "image", f"ProviderError: {exc}")
        except (RuntimeMissing, IncompatibleRuntime) as exc:
            _record(FAIL, "image", f"{type(exc).__name__}: {exc}")
        except Exception as exc:
            _record(FAIL, "image", f"{type(exc).__name__}: {exc}")


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
    await check_storage()
    await check_runtime()
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
