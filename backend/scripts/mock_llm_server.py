"""本地 mock 规划模型：实现 OpenAI 兼容的 /v1/chat/completions。

用途：让「智能体对话」在完全离线的 mock 模式下可跑通。
它不调用任何厂商接口，只按规则把用户指令映射到已注册的工具，
返回 OpenAI 协议的工具调用。后端拿到的东西与真实模型完全同构，
因此规划链路（校验、确认、排队、逐步执行）在 mock 下也能被测到。

用法：
    python scripts/mock_llm_server.py --port 7300

在后台「模型配置」里把它登记为 openai_compat 文本连接，
base URL 填 http://127.0.0.1:7300/v1，并注意 ALLOWED_PROVIDER_HOSTS 要放行本地。

指令到工具的映射规则：
1. 显式指定：消息里写 [@tool=adjust_image] 时直接用该工具。
2. 关键词匹配：按下表从前往后命中第一个。
3. 兜底：当成 generate_image，提示词取整句。

多步计划：写多个 [@tool=...] 时按出现顺序返回多个工具调用，
用于触发「确认后开始」那条路径。
"""

import argparse
import json
import re
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# 关键词 -> (工具名, 参数构造)。命中多条时取「匹配到的最长关键词」那条，
# 所以同长度的规则按表内先后顺序决胜。参数构造函数收到用户原句，返回该工具的入参。
_RULES: list[tuple[str, str, object]] = []


def _rule(keywords: str, tool: str, builder=None) -> None:
    _RULES.append((keywords, tool, builder))


def _adjust_params(goal: str) -> dict:
    """把调色词拆成具体参数，缺省给一个温和的亮度调整。"""
    params: dict[str, float] = {}
    if "提亮" in goal or "变亮" in goal or "亮一点" in goal:
        params["brightness"] = 0.25
    if "压暗" in goal or "变暗" in goal or "暗一点" in goal:
        params["brightness"] = -0.25
    if "对比" in goal:
        params["contrast"] = 0.3
    if "饱和" in goal:
        params["saturation"] = 0.3
    if "锐化" in goal:
        params["sharpness"] = 0.3
    if "冷" in goal:
        params["temperature"] = -0.25
    if "暖" in goal:
        params["temperature"] = 0.25
    if "晕影" in goal:
        params["vignette"] = 0.4
    if not params:
        params["brightness"] = 0.2
    return params


def _marketing_params(goal: str) -> dict:
    if "模特" in goal:
        kind = "model"
    elif "海报" in goal:
        kind = "poster"
    elif "场景" in goal:
        kind = "scene"
    else:
        kind = "product"
    return {"kind": kind, "count": 1, "ratio": "1:1"}


def _ratio_params(goal: str) -> dict:
    ratios = [r for r in ("9:16", "4:5", "1:1", "16:9", "3:4") if r in goal]
    return {"ratios": ratios or ["1:1", "4:5", "9:16"]}


def _flip_params(goal: str) -> dict:
    return {"direction": "vertical" if "垂直" in goal or "上下" in goal else "horizontal"}


# 关键词用空格分隔。命中多条时取「匹配到的最长关键词」那条，
# 同长度按表内先后决胜——所以更长的说法要写全，避免被短词抢走。
_rule("去背景 抠图 抠出主体 移除背景 去掉背景 去除背景 背景去掉 背景去除", "remove_background")
_rule("换背景 替换背景 背景换成 背景替换", "replace_background", lambda g: {"prompt": g, "count": 1})
_rule("扩图 扩展画面 拓展画面", "expand_canvas", lambda g: {"prompt": g})
_rule("放大 超分 清晰度提升", "upscale_image", lambda g: {"scale": 2})
_rule("消除 擦掉 去除杂物", "erase_region")
_rule("替换 改成 换成", "replace_region", lambda g: {"prompt": g})
_rule("拆层 分离图层", "split_layers")
_rule("独立成层 提取物体 抠出物体", "promote_object_to_layer")
_rule("主图 营销图 模特图 海报 场景图 商品图", "generate_marketing", _marketing_params)
_rule("尺寸 物料 投放 规格图", "prepare_delivery_sizes", _ratio_params)
_rule("裁切 裁剪", "crop_canvas", lambda g: {"ratio": "1:1"})
_rule("翻转 镜像", "flip_layer", _flip_params)
_rule("不透明度 透明度", "set_layer_opacity", lambda g: {"opacity": 0.5})
_rule("隐藏 隐藏图层", "set_layer_visible", lambda g: {"visible": False})
_rule("显示 显示图层", "set_layer_visible", lambda g: {"visible": True})
_rule("文案 改文字 换文字 文字内容", "set_layer_text", lambda g: {"text": g[:100]})
_rule("置顶 层级 上移 下移", "reorder_layer", lambda g: {"place": "top"})
_rule("缩放图层", "scale_layer", lambda g: {"factor": 1.2})
_rule("旋转 转个角度", "rotate_layer", lambda g: {"angle": 90})
_rule("移动图层", "move_layer", lambda g: {"dx": 20, "dy": 0})
_rule("调色 提亮 变亮 变暗 压暗 饱和度 对比度 锐化 冷色 暖色 晕影", "adjust_image", _adjust_params)
_rule("批量", "batch_process", lambda g: {"asset_ids": [], "operations": [], "formats": ["png"]})

_EXPLICIT = re.compile(r"\[@tool=([a-z_]+)\]")


def _pick_tools(goal: str) -> list[tuple[str, dict]]:
    """把用户原句解析成 (工具名, 参数) 列表。"""
    explicit = _EXPLICIT.findall(goal)
    if explicit:
        return [(name, _default_args(name, goal)) for name in explicit]

    # 取最长匹配：说「把背景去掉」时，「背景去掉」比「去背景」更能说明意图
    best: tuple[int, str, object] | None = None
    for keywords, tool, builder in _RULES:
        for word in keywords.split():
            if word in goal and (best is None or len(word) > best[0]):
                best = (len(word), tool, builder)
    if best is not None:
        builder = best[2]
        args = builder(goal) if callable(builder) else {}
        return [(best[1], args)]
    return [("generate_image", {"prompt": goal, "count": 1, "ratio": "1:1"})]


def _default_args(tool: str, goal: str) -> dict:
    """显式指定工具时补一份合法的默认入参。"""
    for keywords, name, builder in _RULES:
        if name == tool:
            return builder(goal) if callable(builder) else {}
    return {"prompt": goal, "count": 1, "ratio": "1:1"}


def _last_human_message(payload: dict) -> str:
    """取出最后一条用户消息的正文。"""
    for message in reversed(payload.get("messages") or []):
        if message.get("role") != "user":
            continue
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = [b.get("text", "") for b in content if isinstance(b, dict)]
            return "".join(parts)
    return ""


def _completion(content: str, tool_calls: list[dict]) -> dict:
    message: dict = {"role": "assistant", "content": content}
    finish = "stop"
    if tool_calls:
        message["tool_calls"] = tool_calls
        message["content"] = content or None
        finish = "tool_calls"
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "mock-planner",
        "choices": [{"index": 0, "message": message, "finish_reason": finish}],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args) -> None:  # noqa: A002 - 覆写父类签名
        print(f"[mock-llm] {fmt % args}")

    def _reply(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler 约定
        if self.path.rstrip("/") in ("/v1/models", "/models"):
            self._reply(
                {
                    "object": "list",
                    "data": [
                        {
                            "id": "mock-planner",
                            "object": "model",
                            "created": int(time.time()),
                            "owned_by": "local",
                        }
                    ],
                }
            )
            return
        self._reply({"error": {"message": "not found"}}, 404)

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler 约定
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._reply({"error": {"message": "invalid json"}}, 400)
            return

        if self.path.rstrip("/") not in ("/v1/chat/completions", "/chat/completions"):
            self._reply({"error": {"message": "not found"}}, 404)
            return

        goal = _last_human_message(payload)
        tools = payload.get("tools") or []

        # 没有工具时是纯文本问答（后台「连通性测试」走的就是这条）
        if not tools:
            self._reply(_completion("就绪", []))
            return

        picked = _pick_tools(goal)
        tool_calls = []
        for name, args in picked:
            tool_calls.append(
                {
                    "id": f"call_{uuid.uuid4().hex[:12]}",
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": json.dumps(args, ensure_ascii=False),
                    },
                }
            )
        print(f"[mock-llm] goal={goal!r} -> {[c['function']['name'] for c in tool_calls]}")
        self._reply(_completion("", tool_calls))


def main() -> int:
    parser = argparse.ArgumentParser(description="本地 mock 规划模型（OpenAI 兼容）")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7300)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"[mock-llm] 监听 http://{args.host}:{args.port}/v1")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[mock-llm] 已停止")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
