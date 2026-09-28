import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import agent
from app.layers import LayerDocument
from app.models import AgentRun, EditSession
from app.models.tool_run import RunStatus
from app.services import assets

logger = logging.getLogger(__name__)


async def describe(session: AsyncSession, record: EditSession) -> str:
    """给规划模型的画布摘要，只给决策必需的事实。"""

    document = LayerDocument.model_validate(record.document)
    parts = [
        f"画幅 {document.width}×{document.height}",
        f"图层 {len(document.layers)} 个",
        f"修订号 {record.revision}",
    ]

    # 模型看不到数据库，只能读到这段文字，所以不能靠它自己反推画布长什么样
    current = await assets.get_for_user(session, record.user_id, record.current_asset_id)
    if current is not None:
        # 有没有透明通道决定了后续哪些工具可用（比如去背景），所以一并说明
        parts.append(f"当前图 {current.image_format}{'，含透明通道' if current.has_alpha else ''}")
    return "；".join(parts)


async def respond(session: AsyncSession, record: EditSession, goal: str) -> AgentRun:
    """规划一轮指令并落库。规划失败也记录成一轮对话，不对用户隐瞒失败。"""
    # 必须在下发之前取：agent.run 内部会执行工具，工具落库时会顺带把 record.revision 顶上去，
    # 事后取就记成改完之后的号，这轮对话就对不上它发出时的画布了
    revision = record.revision
    reply, plan, error = "", [], None

    try:
        # 这三样是工具执行时需要的上下文（读素材的归属、往哪个会话里写），由 graph 在下发时取用
        deps = agent.AgentDeps(session=session, user_id=record.user_id, session_id=record.id)
        reply, plan = await agent.run(goal, await describe(session, record), deps)
    except agent.PlannerUnavailable as exc:
        # 模型没配或调不通，异常信息本身可以给用户看（如「未配置模型」），原样带出去
        error = str(exc)
    except Exception:
        # 意料之外的异常只记日志，回给前端一句通用提示，避免泄露堆栈
        logger.exception("指令规划异常 session_id=%s", record.id)
        await session.rollback()
        error = "规划失败，请重试"

    # 失败也落库：对话历史要完整，前端据此显示这一轮失败了以及失败原因
    turn = AgentRun(
        user_id=record.user_id,
        session_id=record.id,
        revision=revision,
        goal=goal,
        reply=reply,
        # 存的是校验并执行后的计划，每步带 run_id，前端拿它订阅 SSE 看进度
        plan=plan,
        status=RunStatus.FAILED if error else RunStatus.SUCCEEDED,
        error=error,
    )
    session.add(turn)
    await session.commit()
    await session.refresh(turn)
    return turn


async def turns_of(session: AsyncSession, record: EditSession, limit: int = 50) -> list[AgentRun]:
    """按时间顺序取最近的对话记录，默认 50 条，供聊天区回填。"""

    result = await session.scalars(
        select(AgentRun)
        .where(AgentRun.session_id == record.id)
        .order_by(AgentRun.created_at)
        .limit(limit)
    )
    return list(result)