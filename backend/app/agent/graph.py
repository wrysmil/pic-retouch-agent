from functools import lru_cache
from typing import TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from app.agent.llm import planner
from app.agent.plan import PlanError, validate
from app.services import tools as tool_service
from app.tools import UnknownTool, label_of

# 规划模型的系统提示词。{context} 由 services/agent.describe() 填当前画布摘要
_SYSTEM = """你是电商图片修图助手，通过调用工具完成用户的修图请求。

规则：
- 只能使用已提供的工具。可以一次安排多步，按完成先后调用；后一步默认依赖前一步。
- 能一步完成的不要拆成多步，最多 8 步。
- 缺失参数用画布信息与常识补齐，可推断的参数不要反问用户。
- 图层与选区是两个独立维度：layer_id 决定改哪一层，选区决定改哪块区域。
  用户点名了图层（如「物体2」「背景」「主体」）就把它的 id 或名字填进 layer_id。
- 画布摘要标明已有选区时，那就是用户要改的物体：局部消除、替换、提升为图层
  直接调用，不要再让用户重选，也不要猜测选区是否点准。没有选区也能调用，
  此时作用在整个目标图层。
- 一句话要改多个图层时，按图层拆成多步，每步只填一个 layer_id。
- 改颜色、换材质、换成某物用 replace_region 并点名 layer_id；
  只改整张背景才用 replace_background。adjust_image 只做明暗冷暖，不做改色。
- 翻转画面用 flip_layer；说了角度用 rotate_layer。
- 用户要求拆层、把物体独立成层时，使用 split_layers 或 promote_object_to_layer。
- 拆层默认不拆文字，只有用户明确要求时才传 include_text。
- 出营销图、主图、场景图、模特图、海报用 generate_marketing，
  kind 分别为 product / scene / model / poster。结果只进图片墙。
- 改尺寸、出投放物料、出 1:1 / 4:5 / 9:16 用 prepare_delivery_sizes，
  不要裁切主体，也不要用 crop_canvas。
- 对多张图做同一套去背景、换背景、调色、超分、扩图或改尺寸时用 batch_process。
  单张精修、营销图、局部编辑和拆层不要用它。
- 调用工具时不要输出解释或工具名。只有指令与修图无关、或现有工具确实做不到时，
  才用一句中文说明，不要提内部参数。

当前画布：{context}"""

# 模型可能只回 tool_calls 而没有正文（或反过来），此时需要一句能直接显示的话兜底
_FALLBACK_REPLY = "没太理解这条指令，换个说法或说得更具体一些。"
# 拒绝语只该是一句话，超出这个长度就当作模型开始讲道理了，截掉
_REFUSAL_LIMIT = 60


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
    """调模型规划一轮：把画布摘要与用户指令一次性发给它，拿回工具调用。"""

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
    """模型给出的计划一律经服务端校验，不可直接执行。

    校验含三件事：工具存在、参数合该工具的入参模型、依赖结构成环与步数上限。
    任何一项不过就整轮作废而不是跳过这一步：宁可什么都不做，也不带着
    残缺的依赖关系往下跑。
    """

    try:
        return {"plan": validate(state["plan"])}
    except (UnknownTool, tool_service.InvalidParams, PlanError) as exc:
        return {"plan": [], "reply": f"这一步暂时执行不了：{exc}"}


@lru_cache
def _graph():
    """编译并缓存图。图的拓扑是静态的，编译一次即可，反复调用不再付出构建成本。"""

    builder = StateGraph(AgentState)
    builder.add_node("plan", _plan)
    builder.add_node("verify", _verify)

    builder.add_edge(START, "plan")
    builder.add_edge("plan", "verify")
    builder.add_edge("verify", END)
    return builder.compile()


async def run(goal: str, context: str) -> tuple[str, list[dict]]:
    """规划并校验一轮指令，返回答复与尚未下发的计划。

    图里不再下发工具：计划要先落库，多步时停住等用户确认，
    真正的执行由 services/agent 按依赖逐步推进。
    """

    state = await _graph().ainvoke({"goal": goal, "context": context, "plan": [], "reply": ""})
    return spoken(state["reply"], state["plan"]), state["plan"]


def spoken(reply: str, plan: list[dict]) -> str:
    """有计划就按步骤说话；没计划才用兜底或截成一句拒绝。

    模型有时会边调工具边讲解，甚至把参数名说出来，那些话对用户没有信息量。
    步骤标签本身就是最准确的说明。
    """

    text = (reply or "").strip()
    if plan:
        if text and text != _FALLBACK_REPLY:
            return text
        labels = "、".join(label_of(step["tool"]) for step in plan)
        if len(plan) > 1:
            return f"将按以下步骤执行：{labels}。确认后开始。"
        return f"好，正在{labels}。"
    return _one_sentence(text) if text else _FALLBACK_REPLY


def _one_sentence(text: str) -> str:
    """取正文的第一句。中文句号、感叹号、问号与换行都算断句。"""

    for sep in ("。", "！", "？", "\n"):
        head, found, _ = text.partition(sep)
        if found and head.strip():
            return head.strip() + (sep if sep != "\n" else "。")
    if len(text) > _REFUSAL_LIMIT:
        return text[:_REFUSAL_LIMIT].rstrip() + "…"
    return text


def _text_of(message: AIMessage) -> str:
    """取模型的正文。content 是 str 就直接用，是列表则只拼文本块。"""

    if isinstance(message.content, str):
        return message.content.strip()
    # 部分模型返回分块内容，只取文本块
    return "".join(
        block.get("text", "") for block in message.content if isinstance(block, dict)
    ).strip()
