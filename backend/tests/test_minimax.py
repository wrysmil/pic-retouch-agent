"""MiniMax 文本适配器的离线单测：不联网、不落库。

用例只覆盖「协议参数怎么算出来」与「后台入参是否接受 minimax」，
真实连通性由后台「模型配置 → 连通性测试」按需触发。

注意：tests/conftest.py 的 session fixture 会清空开发库里的连接与运行版本，
只想跑这些纯函数用例时可以跳过 conftest：

    uv run pytest tests/test_minimax.py --noconftest -q
"""

import pytest
from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from app.models import AdapterType
from app.schemas.admin_config import AdminConnectionCreate
from app.services.model_runtime import (
    IncompatibleRuntime,
    _build_image_provider,
    _planner_options,
    _resolve_planner_base,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://api.minimax.cn", "https://api.minimax.cn/v1"),
        ("https://api.minimax.cn/", "https://api.minimax.cn/v1"),
        ("https://api.minimax.cn/v1", "https://api.minimax.cn/v1"),
        ("https://api.minimax.cn/v1/", "https://api.minimax.cn/v1"),
        # 管理员可能直接把文档里的完整 POST 地址粘进来
        ("https://api.minimax.cn/v1/chat/completions", "https://api.minimax.cn/v1"),
    ],
)
def test_minimax_base_url_is_normalized(raw: str, expected: str):
    assert _resolve_planner_base(AdapterType.MINIMAX, raw) == expected


def test_other_adapters_keep_their_own_base_url_rules():
    # OpenAI 兼容连接的 base 由管理员填全，adapter 不改写
    assert (
        _resolve_planner_base(AdapterType.OPENAI_COMPAT, "https://api.openai.com/v1")
        == "https://api.openai.com/v1"
    )
    # 百炼仍然要追加兼容模式路径
    assert (
        _resolve_planner_base(AdapterType.DASHSCOPE, "https://dashscope.aliyuncs.com")
        == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )


def test_minimax_always_asks_to_split_reasoning():
    """不拆分的话思考会以 <think> 内联在 content 里，跟着规划正文一起显示给用户。"""
    assert _planner_options(AdapterType.MINIMAX, {})["extra_body"] == {"reasoning_split": True}


def test_minimax_reasoning_effort_comes_from_param_schema():
    options = _planner_options(AdapterType.MINIMAX, {"reasoning_effort": "low"})
    assert options["reasoning_effort"] == "low"
    # 非法值不下发，退回厂商默认（M3.1-Flash 是 max）
    bad = _planner_options(AdapterType.MINIMAX, {"reasoning_effort": "none"})
    assert "reasoning_effort" not in bad
    assert "reasoning_effort" not in _planner_options(AdapterType.MINIMAX, None)


def test_other_adapters_get_no_minimax_options():
    assert _planner_options(AdapterType.OPENAI_COMPAT, {"reasoning_effort": "low"}) == {}
    assert _planner_options(AdapterType.DASHSCOPE, None) == {}


def test_minimax_params_reach_the_request_payload():
    """按 _build_planner 的方式构造客户端，确认参数真落在请求体里。"""
    options = _planner_options(AdapterType.MINIMAX, {"reasoning_effort": "low"})
    client = ChatOpenAI(
        model="MiniMax-M3.1-Flash",
        api_key="test-key",
        base_url=_resolve_planner_base(AdapterType.MINIMAX, "https://api.minimax.cn"),
        temperature=0,
        **options,
    )
    params = client._default_params  # langchain-openai 实际下发的字段
    assert params["model"] == "MiniMax-M3.1-Flash"
    assert params["temperature"] == 0
    assert params["reasoning_effort"] == "low"
    assert params["extra_body"] == {"reasoning_split": True}


def test_minimax_is_rejected_for_the_image_slot():
    """MiniMax 只接文本；生图槽位绑定它时要给出可读原因。"""
    with pytest.raises(IncompatibleRuntime, match="只支持文本"):
        _build_image_provider(AdapterType.MINIMAX, None, "MiniMax-M3.1-Flash", None)


def test_admin_schema_accepts_minimax_adapter():
    body = AdminConnectionCreate(
        slug="minimax-main",
        vendor="minimax",
        adapter_type="minimax",
        display_name="MiniMax 文本",
        base_url="https://api.minimax.cn/v1",
        api_key="test-key",
    )
    assert AdapterType(body.adapter_type) is AdapterType.MINIMAX


def test_admin_schema_still_rejects_unknown_adapters():
    with pytest.raises(ValidationError):
        AdminConnectionCreate(
            slug="minimax-typo",
            vendor="minimax",
            adapter_type="minimaxx",
            display_name="typo",
            base_url="https://api.minimax.cn/v1",
            api_key="test-key",
        )
