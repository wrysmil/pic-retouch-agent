import uuid
from dataclasses import dataclass
from functools import lru_cache
from typing import TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.llm import planner
from app.services import tools as tool_service
from app.tools import UnknownTool, label_of, spec_of

# 规划模型的系统提示词。{context} 由 services/agent.describe() 填当前画布摘要
_SYSTEM = """你是电商图片修图助手，通过调用工具完成用户的修图请求。

规则：
- 只能使用已提供的工具，本轮最多安排一步。
- 缺失参数用画布信息与常识补齐，可推断的参数不要反问用户。
- 画布摘要标明已有选区时，局部消除/替换可直接调用，不要再让用户重选。
- 指令与修图无关，或现有工具做不到时，用一句中文说明原因，不要调用工具。

当前画布：{context}"""

# 模型可能只回 tool_calls 而没有正文（或反过来），此时需要一句能直接显示的话兜底
_FALLBACK_REPLY = "没太理解这条指令，换个说法或说得更具体一些。"


@dataclass(frozen=True)
class AgentDeps:
    """图执行所需的运行时依赖。不放进 state，以便后续接入 checkpoint。"""

    session: AsyncSession
    user_id: uuid.UUID
    session_id: uuid.UUID


class AgentState(TypedDict):
    """图内流转的状态字典。

    各节点只返回自己改动的 key，LangGraph 按 key 覆盖合并，
    所以不需要每个节点都把整个 state 原样回传。
    """

    goal: str
    context: str
    plan: list[dict]
    reply: str


async def _plan(state: AgentState) -> AgentState:
    """调模型规划一步：把画布摘要与用户指令一次性发给它，拿回工具调用。"""

    # 每次都是全新的两条消息，不带历史，模型对上一轮无记忆
    message = await planner().ainvoke(
        [
            SystemMessage(_SYSTEM.format(context=state["context"])),
            HumanMessage(state["goal"]),
        ]
    )
    # 模型的 tool_calls 是 [{'name','args','id'}]，只留前两个字段，id 等执行期信息用不上
    return {
        "plan": [{"tool": call["name"], "params": call["args"]} for call in message.tool_calls],
        "reply": _text_of(message),
    }


def _verify(state: AgentState) -> AgentState:
    """模型给出的计划一律经服务端校验，不可直接执行。"""

    checked: list[dict] = []
    for step in state["plan"]:
        try:
            spec = spec_of(step["tool"])
            # 用 tools.submit 同一套校验，模型填错参数在这里就拦下，不会走到落库
            params = tool_service.validate(spec.name, step["params"])
        except (UnknownTool, tool_service.InvalidParams) as exc:
            # 整个计划作废而不是跳过这一步：单步执行没有中间态可站，宁可什么都不做
            return {"plan": [], "reply": f"这一步暂时执行不了：{exc}"}
        checked.append({"tool": spec.name, "params": params})
    return {"plan": checked}


async def _dispatch(state: AgentState, config: RunnableConfig) -> AgentState:
    """下发已校验的计划。画布工具当场跑完，像素工具返回时还在排队。"""

    # deps 走 RunnableConfig 而不是 state：它是运行时依赖，不该被当成图状态存下来
    deps: AgentDeps = config["configurable"]["deps"]

    plan: list[dict] = []
    for step in state["plan"]:
        # 与界面点击同一个入口：submit 内部决定是当场执行还是入队
        run = await tool_service.submit(
            deps.session, deps.user_id, step["tool"], step["params"], deps.session_id
        )
        # 带上 run_id，前端据此订阅 SSE 看这一部的进度与结果
        plan.append(step | {"run_id": str(run.id)})

    # 模型没写正文时自己拼一句，措辞用工具的中文标签而不是内部名字
    labels = "、".join(label_of(step["tool"]) for step in plan)
    return {"plan": plan, "reply": state["reply"] or f"好，正在{labels}。"}


def _has_plan(state: AgentState) -> str:
    """条件边：校验后还有计划才继续下发，否则就地结束。

    模型认为指令与修图无关时会直接给一句话、不调工具，此时 plan 为空。
    """

    return "dispatch" if state["plan"] else END


@lru_cache
def _graph():
    """编译并缓存图。图的拓扑是静态的，编译一次即可，反复调用不再付出构建成本。"""

    builder = StateGraph(AgentState)
    builder.add_node("plan", _plan)
    builder.add_node("verify", _verify)
    builder.add_node("dispatch", _dispatch)

    builder.add_edge(START, "plan")
    builder.add_edge("plan", "verify")
    # verify 之后是唯一的分岔：计划非空走下发，为空直接收尾
    builder.add_conditional_edges("verify", _has_plan, {"dispatch": "dispatch", END: END})
    builder.add_edge("dispatch", END)
    return builder.compile()


async def run(goal: str, context: str, deps: AgentDeps) -> tuple[str, list[dict]]:
    """规划并下发一轮指令，返回给用户的答复与已下发的计划。"""

    state = await _graph().ainvoke(
        # 初始 plan/reply 必须是全的：后面有节点只返回部分 key，缺键会读不到
        {"goal": goal, "context": context, "plan": [], "reply": ""},
        config={"configurable": {"deps": deps}},
    )
    return state["reply"] or _FALLBACK_REPLY, state["plan"]


def _text_of(message: AIMessage) -> str:
    """取模型的正文。content 是 str 就直接用，是列表则只拼文本块。"""

    if isinstance(message.content, str):
        return message.content.strip()
    # 部分模型返回分块内容，只取文本块
    return "".join(
        block.get("text", "") for block in message.content if isinstance(block, dict)
    ).strip()
