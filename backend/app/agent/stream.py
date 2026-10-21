"""规划模型的流式读取。

只把工具调用片段聚合成公开草稿；完整工具调用仍要经过 plan.validate 才能执行。
模型不支持流式时降级为一次完整返回，不伪造逐字输出。
"""

import json
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agent.graph import _SYSTEM, _text_of
from app.agent.llm import bind_tools
from app.tools import label_of

DraftCallback = Callable[[dict], Awaitable[None]]

logger = logging.getLogger(__name__)

# 草稿里只展示用户能理解、且不涉及内部遮罩/种子/参考图的参数
_PREVIEW_KEYS = ("prompt", "count", "ratio", "kind", "layer_id", "scale", "direction")
_PREVIEW_TEXT = 48
_THROTTLE = 0.12


def _preview(args: dict) -> dict:
    preview: dict[str, Any] = {}
    for key in _PREVIEW_KEYS:
        if key not in args:
            continue
        value = args[key]
        if key == "prompt" and isinstance(value, str):
            value = value[:_PREVIEW_TEXT]
        preview[key] = value
    return preview


def _partial_json(text: str) -> dict:
    """流式参数永远是半截 JSON：能解析就用，解析不了就先不展示。"""
    if not text.strip():
        return {}
    try:
        value = json.loads(text)
    except (ValueError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def _draft(index: int, name: str, args_text: str) -> dict:
    args = _partial_json(args_text)
    return {
        "call_index": index,
        "id": f"d{index + 1}",
        "tool": name,
        "label": label_of(name, args),
        "params": _preview(args),
        "state": "draft",
    }


def _text_of_chunk(chunk: Any) -> str:
    content = getattr(chunk, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") in {None, "text"}
        )
    return ""


async def stream_plan(
    goal: str,
    context: str,
    planner: Any,
    on_draft: DraftCallback,
    on_text: Callable[[str], Awaitable[None]] | None = None,
) -> tuple[str, list[dict]]:
    """返回 (模型正文, 未校验的工具调用列表)。

    on_draft 收到的是公开草稿；它没有执行权限，校验失败时由调用方撤回。
    on_text 收到模型的公开说明增量，用于逐字展示。
    """

    bound = bind_tools(planner)
    messages = [SystemMessage(_SYSTEM.format(context=context)), HumanMessage(goal)]

    if not hasattr(bound, "astream"):
        message = await bound.ainvoke(messages)
        return _text_of(message), _calls_of(message)

    calls: dict[int, dict] = {}
    emitted: dict[int, tuple[str, str]] = {}
    last_at: dict[int, float] = {}
    aggregate = None
    received = False

    try:
        async for chunk in bound.astream(messages):
            received = True
            aggregate = chunk if aggregate is None else aggregate + chunk
            if on_text is not None:
                delta = _text_of_chunk(chunk)
                if delta:
                    await on_text(delta)
            for raw in getattr(chunk, "tool_call_chunks", None) or []:
                index = int(raw.get("index") or 0)
                entry = calls.setdefault(
                    index, {"id": raw.get("id") or "", "name": "", "args": ""}
                )
                if raw.get("name") and not entry["name"]:
                    entry["name"] = raw["name"]
                if raw.get("args"):
                    entry["args"] += raw["args"]
                if not entry["name"]:
                    continue
                draft = _draft(index, entry["name"], entry["args"])
                fingerprint = (draft["tool"], json.dumps(draft["params"], sort_keys=True))
                now = time.monotonic()
                if emitted.get(index) == fingerprint:
                    continue
                if index in emitted and now - last_at.get(index, 0) < _THROTTLE:
                    continue
                emitted[index] = fingerprint
                last_at[index] = now
                await on_draft(draft)
    except Exception:
        # 已经收到过片段说明不是「不支持流式」，不能再次调用模型造成重复计费
        if received:
            raise
        logger.warning("模型流式不可用，降级为一次完整调用", exc_info=True)
        message = await bound.ainvoke(messages)
        return _text_of(message), _calls_of(message)

    text = _text_of(aggregate) if isinstance(aggregate, AIMessage) else ""
    raw_plan = _aggregate_calls(calls)
    if not raw_plan and isinstance(aggregate, AIMessage):
        # 部分模型只给完整 tool_calls，不给 tool_call_chunks
        raw_plan = _calls_of(aggregate)
    if not raw_plan and not text.strip():
        # 流式完全没有可用内容：降级成一次完整调用来拿计划
        message = await bound.ainvoke(messages)
        return _text_of(message), _calls_of(message)
    return text, raw_plan


def _calls_of(message: AIMessage) -> list[dict]:
    return [
        {"tool": call["name"], "params": call.get("args") or {}}
        for call in getattr(message, "tool_calls", None) or []
    ]


def _aggregate_calls(calls: dict[int, dict]) -> list[dict]:
    result: list[dict] = []
    for index in sorted(calls):
        entry = calls[index]
        name = entry.get("name") or ""
        if not name:
            continue
        result.append({"tool": name, "params": _partial_json(entry.get("args") or "")})
    return result
