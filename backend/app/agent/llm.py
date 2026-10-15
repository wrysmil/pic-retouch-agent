from langchain_core.utils.function_calling import convert_to_openai_function
from langchain_openai import ChatOpenAI

from app.tools import SPECS, ToolSpec


class PlannerUnavailable(Exception):
    """规划模型未配置或不可用。"""


def _schema_of(spec: ToolSpec) -> dict:
    """把工具参数模型转成 OpenAI function schema，并隐藏不应交给模型的字段。"""
    function = convert_to_openai_function(spec.params)
    function["name"] = spec.name
    function["description"] = spec.description

    parameters = function.get("parameters", {})
    for hidden in spec.agent_hidden:
        parameters.get("properties", {}).pop(hidden, None)
    parameters["required"] = [
        name for name in parameters.get("required", []) if name not in spec.agent_hidden
    ]
    return {"type": "function", "function": function}


def planner_tools() -> list[dict]:
    """返回全部已注册工具的 OpenAI function schema。供运行时按发布版本绑定。"""
    return [_schema_of(spec) for spec in SPECS]


def bind_tools(client: ChatOpenAI) -> ChatOpenAI:
    """按工具规格把 client 重新绑定。client 应来自 services/model_runtime 解析的版本。"""
    return client.bind_tools(planner_tools())