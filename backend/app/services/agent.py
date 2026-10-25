import logging
import time
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app import agent
from app.agent import plan as plan_mod
from app.agent.graph import spoken
from app.agent.stream import stream_plan
from app.config import get_settings
from app.layers import Layer, LayerDocument, LayerKind
from app.models import AgentPhase, AgentRun, EditSession, ToolRun
from app.models.tool_run import RunStatus
from app.queue import enqueue
from app.services import assets, quota, runs, selections, sessions, tools, turn_events
from app.tools import UnknownTool, spec_of

logger = logging.getLogger(__name__)

# 文字流合并窗口：太密会把数据库写满，太疏会看出卡顿
_SUMMARY_THROTTLE = 0.1


class TurnNotFound(Exception):
    """指定 id 的对话不属于这个会话。"""


class CannotConfirm(Exception):
    """这轮没有停在待确认的步骤。"""


class CannotCancel(Exception):
    """这轮已经结束，没有可取消的步骤。"""


class CannotRetry(Exception):
    """这轮没有失败的步骤。"""


class IdempotencyConflict(Exception):
    """同一个请求键被用于了不同内容。"""


PLAN_TASK = "plan_turn"


def phase_of(turn: AgentRun, steps: list[dict] | None = None) -> AgentPhase:
    """把旧 status 投影成真实阶段，供兼容路径与状态变更后统一使用。"""

    if turn.error:
        return AgentPhase.FAILED
    status = turn.status
    if status == RunStatus.SUCCEEDED:
        return AgentPhase.COMPLETED
    if status == RunStatus.FAILED:
        return AgentPhase.FAILED
    if status == RunStatus.CANCELED:
        return AgentPhase.CANCELED
    if status == RunStatus.QUEUED:
        waiting = any(
            step.get("status") == plan_mod.WAITING for step in (steps or turn.plan or [])
        )
        return AgentPhase.AWAITING_CONFIRMATION if waiting else AgentPhase.EXECUTING
    return AgentPhase.EXECUTING


def _apply_phase(turn: AgentRun, steps: list[dict]) -> None:
    turn.phase = phase_of(turn, steps)



async def describe(session: AsyncSession, record: EditSession) -> str:
    """给规划模型的画布摘要，只给决策必需的事实。"""

    document = LayerDocument.model_validate(record.document)
    names = [_layer_name(layer) for layer in document.layers]
    parts = [
        f"画幅 {document.width}×{document.height}",
        f"图层 {len(document.layers)} 个，自下而上（{'、'.join(names)}）",
        "layer_id 填图层 id 或名字；不填则作用在选区下最上层图像，换背景作用在背景层",
        f"修订号 {record.revision}",
    ]

    # 模型看不到数据库，只能读到这段文字，所以不能靠它自己反推画布长什么样
    current = await assets.get_for_user(session, record.user_id, record.current_asset_id)
    if current is not None:
        # 有没有透明通道决定了后续哪些工具可用（比如去背景），所以一并说明
        parts.append(f"当前图 {current.image_format}{'，含透明通道' if current.has_alpha else ''}")

    # 有没有选区决定了局部工具能不能直接调用，模型看不到画布，只能靠这段文字
    selected = await selections.get(record.id, record.revision)
    if selected:
        markers = selected.get("markers") or []
        where = f"已有选区，{len(markers)} 个标点" if markers else "已有笔刷选区"
        parts.append(f"{where}（选区只限定区域，不限定图层；与 layer_id 同时给出时取交集）")
    else:
        parts.append("当前无选区，区域工具会作用在整个图层")
    return "；".join(parts)


def _layer_name(layer: Layer) -> str:
    text = f"文字「{layer.text[:8]}」" if layer.kind is LayerKind.TEXT and layer.text else None
    name = f"{layer.id}={text or layer.name}"
    return name if layer.visible else f"{name}·隐藏"


async def create_turn(
    session: AsyncSession,
    record: EditSession,
    goal: str,
    request_id: str | None = None,
) -> AgentRun:
    """先落一轮 planning 状态的对话，再交给 worker 规划。

    request_id 是用户级幂等键：重复点击返回原轮次，同键不同内容视为冲突。
    """

    if request_id:
        existing = await session.scalar(
            select(AgentRun).where(
                AgentRun.user_id == record.user_id,
                AgentRun.idempotency_key == request_id,
            )
        )
        if existing is not None:
            if existing.goal.strip() != goal.strip():
                raise IdempotencyConflict
            return existing

    turn = AgentRun(
        user_id=record.user_id,
        session_id=record.id,
        revision=record.revision,
        goal=goal,
        reply="",
        plan=[],
        status=RunStatus.QUEUED,
        phase=AgentPhase.PLANNING,
        idempotency_key=request_id,
        planning_attempt=1,
        plan_draft=[],
        public_summary="正在安排…",
    )
    session.add(turn)
    try:
        async with session.begin_nested():
            await session.flush()
    except IntegrityError:
        if request_id is None:
            raise
        found = await session.scalar(
            select(AgentRun).where(
                AgentRun.user_id == record.user_id,
                AgentRun.idempotency_key == request_id,
            )
        )
        if found is not None and found.goal.strip() == goal.strip():
            return found
        raise IdempotencyConflict from None

    turn.checkpoint_thread_id = f"turn:{turn.id}:{turn.planning_attempt}"
    await session.commit()
    await session.refresh(turn)
    await turn_events.emit(
        session, turn, "planning.started", {"at": datetime.now(UTC).isoformat()}
    )
    try:
        await enqueue(PLAN_TASK, turn.id)
    except Exception:  # pragma: no cover - 队列故障不丢轮次，交恢复扫描/刷新重投
        logger.exception("规划任务投递失败 turn_id=%s", turn.id)
    return turn


async def plan_turn(session: AsyncSession, turn_id: uuid.UUID) -> AgentRun | None:
    """worker 侧真正调用规划模型，并把草稿、正式计划与终态写成事件。"""

    turn = await session.get(AgentRun, turn_id)
    if turn is None or turn.phase != AgentPhase.PLANNING:
        return turn

    # 领取规划租约：并发的重复投递只有一个 worker 能继续，恢复扫描也只捡过期租约
    now = datetime.now(UTC)
    lease = timedelta(seconds=max(30, get_settings().agent_plan_lease_seconds))
    claimed = await session.execute(
        update(AgentRun)
        .where(
            AgentRun.id == turn_id,
            AgentRun.phase == AgentPhase.PLANNING,
            or_(
                AgentRun.planning_lease_until.is_(None),
                AgentRun.planning_lease_until < now,
            ),
        )
        .values(planning_lease_until=now + lease)
        .returning(AgentRun.id)
    )
    if claimed.first() is None:
        return turn
    await session.commit()
    turn = await session.get(AgentRun, turn_id)
    if turn is None:
        return None

    try:
        record = await sessions.load(session, turn.session_id)
    except sessions.SessionNotFound:
        return await _fail_planning(session, turn, "会话不存在，无法继续规划")
    except Exception:
        # 任何意外都要把轮次落到失败态，不能让它永远停在「规划中」
        logger.exception("读取会话失败 turn_id=%s", turn_id)
        await session.rollback()
        turn = await session.get(AgentRun, turn_id)
        if turn is None:
            return None
        return await _fail_planning(session, turn, "规划失败，请重试")

    try:
        # 局部导入：测试通过替换 model_runtime.get_planner 注入假模型
        from app.services.model_runtime import current_version_id, get_planner

        version_id = await current_version_id(session)
        turn.runtime_config_version_id = version_id

        resumed = await _resume_checkpoint(turn)
        if resumed is not None:
            reply, raw = resumed
            steps = plan_mod.validate(raw, goal=turn.goal)
            steps = await _pin_selection(session, record, steps)
            return await _finish_planning(session, turn, reply, steps)

        planner = await get_planner(session, version_id)
        context = await describe(session, record)

        async def on_draft(draft: dict) -> None:
            drafts = [
                item
                for item in (turn.plan_draft or [])
                if item.get("call_index") != draft["call_index"]
            ]
            drafts.append(draft)
            drafts.sort(key=lambda item: item.get("call_index", 0))
            turn.plan_draft = drafts
            await turn_events.emit(
                session, turn, "planning.step.draft", {"draft": draft}
            )

        # 模型的公开说明逐字推送：攒够一段或间隔到阈值再发，避免每个 token 一次事务
        buffer = {"text": "", "last": 0.0}

        async def on_text(delta: str) -> None:
            buffer["text"] += delta
            now = time.monotonic()
            if now - buffer["last"] < _SUMMARY_THROTTLE and len(buffer["text"]) < 120:
                return
            buffer["last"] = now
            turn.public_summary = buffer["text"]
            await turn_events.emit(
                session,
                turn,
                "planning.summary.delta",
                {"text": buffer["text"]},
            )

        reply, raw = await stream_plan(
            turn.goal, context, planner.client, on_draft, on_text
        )
        if buffer["text"] and turn.public_summary != buffer["text"]:
            turn.public_summary = buffer["text"]
            await turn_events.emit(
                session,
                turn,
                "planning.summary.delta",
                {"text": buffer["text"]},
            )

        # 流式期间用户可能已取消规划；取消后不能再把计划写回去执行
        await session.commit()
        await session.refresh(turn)
        if turn.phase != AgentPhase.PLANNING:
            return turn

        steps = plan_mod.validate(raw, goal=turn.goal)
        await _save_checkpoint(turn, context, steps, reply)
        steps = await _pin_selection(session, record, steps)
    except agent.PlannerUnavailable as exc:
        return await _fail_planning(session, turn, str(exc))
    except (UnknownTool, tools.InvalidParams, plan_mod.PlanError) as exc:
        logger.warning("规划校验失败 turn_id=%s plan=%r：%s", turn_id, raw, exc)
        return await _fail_planning(session, turn, f"这一步暂时执行不了：{exc}")
    except Exception:
        logger.exception("指令规划异常 turn_id=%s", turn_id)
        await session.rollback()
        turn = await session.get(AgentRun, turn_id)
        if turn is None:
            return None
        return await _fail_planning(session, turn, "规划失败，请重试")

    return await _finish_planning(session, turn, reply, steps)


async def _finish_planning(
    session: AsyncSession, turn: AgentRun, reply: str, steps: list[dict]
) -> AgentRun:
    turn.reply = spoken(reply, steps, keep_full=True)
    turn.public_summary = turn.reply
    turn.plan = steps
    turn.plan_draft = []
    turn.error = None
    turn.plan_version = (turn.plan_version or 0) + 1
    if plan_mod.needs_confirm(steps):
        turn.status = RunStatus.QUEUED
        turn.phase = AgentPhase.AWAITING_CONFIRMATION
    elif steps:
        turn.status = RunStatus.RUNNING
        turn.phase = AgentPhase.EXECUTING
    else:
        turn.status = RunStatus.SUCCEEDED
        turn.phase = AgentPhase.COMPLETED
    turn.planning_lease_until = None
    _touch(turn)

    await turn_events.commit_and_publish(
        session, turn, "plan.ready", {"turn": await turn_events.snapshot(turn)}
    )

    if turn.status == RunStatus.RUNNING:
        await _advance(session, turn)
    return turn


async def _resume_checkpoint(turn: AgentRun) -> tuple[str, list[dict]] | None:
    """线程里已有规划结果时直接续跑校验，不再调用模型。"""

    from app.agent import checkpoint
    from app.agent.graph import graph_with

    saver = checkpoint.saver()
    if saver is None or not turn.checkpoint_thread_id:
        return None
    try:
        graph = graph_with(saver)
        config = {"configurable": {"thread_id": turn.checkpoint_thread_id}}
        snapshot = await graph.aget_state(config)
        if not snapshot.values.get("plan"):
            return None
        if snapshot.next and "verify" not in snapshot.next:
            # 计划节点本身没跑完，重新流式更可靠
            return None
        state = await graph.ainvoke(None, config) if snapshot.next else snapshot.values
        return state.get("reply", ""), state.get("plan", [])
    except Exception:
        logger.exception("checkpoint 恢复失败 turn_id=%s", turn.id)
        return None


async def _save_checkpoint(
    turn: AgentRun, context: str, steps: list[dict], reply: str
) -> None:
    """把流式得到的计划写进 checkpoint，并执行校验节点。

    模型调用已经完成，这里只持久化结果，不会第二次请求模型。
    """

    from app.agent import checkpoint
    from app.agent.graph import graph_with

    saver = checkpoint.saver()
    if saver is None or not turn.checkpoint_thread_id:
        return
    try:
        graph = graph_with(saver)
        config = {"configurable": {"thread_id": turn.checkpoint_thread_id}}
        await graph.aupdate_state(
            config,
            {
                "turn_id": str(turn.id),
                "goal": turn.goal,
                "context": context,
                "plan": steps,
                "reply": reply,
            },
            as_node="plan",
        )
        await graph.ainvoke(None, config)
    except Exception:
        logger.exception("checkpoint 写入失败 turn_id=%s", turn.id)


async def _fail_planning(
    session: AsyncSession, turn: AgentRun, message: str
) -> AgentRun:
    turn.plan = []
    turn.plan_draft = []
    turn.reply = message
    turn.public_summary = message
    turn.error = message
    turn.status = RunStatus.FAILED
    turn.phase = AgentPhase.FAILED
    turn.planning_lease_until = None
    _touch(turn)
    await turn_events.emit(
        session,
        turn,
        "planning.failed",
        {"message": message, "retryable": True},
    )
    return turn


async def turn_of(
    session: AsyncSession, record: EditSession, turn_id: uuid.UUID
) -> AgentRun:
    return await _get(session, record, turn_id)


async def respond(session: AsyncSession, record: EditSession, goal: str) -> AgentRun:
    """规划一轮指令并落库。多步计划先停住等确认，单步直接开跑。

    规划失败也记录成一轮对话，不对用户隐瞒失败。
    """
    # 必须在下发之前取：工具执行落库时会顺带把 record.revision 顶上去，
    # 事后取就记成改完之后的号，这轮对话就对不上它发出时的画布了
    revision = record.revision
    reply, steps, error = "", [], None
    runtime_version_id: uuid.UUID | None = None

    try:
        # 先把当前生效版本钉下来，后续 graph/工具执行都用这一份
        from app.services.model_runtime import current_version_id, get_planner

        runtime_version_id = await current_version_id(session)
        planner = await get_planner(session, runtime_version_id)
        reply, steps = await agent.run(goal, await describe(session, record), planner.client)
        steps = await _pin_selection(session, record, steps)
    except agent.PlannerUnavailable as exc:
        # 模型没配或调不通，异常信息本身可以给用户看（如「未配置模型」），原样带出去
        error = str(exc)
    except Exception:
        # 意料之外的异常只记日志，回给前端一句通用提示，避免泄露堆栈
        logger.exception("指令规划异常 session_id=%s", record.id)
        await session.rollback()
        error = "规划失败，请重试"

    if error:
        status = RunStatus.FAILED
        phase = AgentPhase.FAILED
    elif plan_mod.needs_confirm(steps):
        # 多步计划整轮停在排队，等用户点「执行计划」；步骤此时还没有 run_id
        status = RunStatus.QUEUED
        phase = AgentPhase.AWAITING_CONFIRMATION
    elif steps:
        status = RunStatus.RUNNING
        phase = AgentPhase.EXECUTING
    else:
        # 模型判定这条指令与修图无关，只回了一句话
        status = RunStatus.SUCCEEDED
        phase = AgentPhase.COMPLETED

    # 失败也落库：对话历史要完整，前端据此显示这一轮失败了以及失败原因
    turn = AgentRun(
        user_id=record.user_id,
        session_id=record.id,
        revision=revision,
        goal=goal,
        reply=reply,
        # 存的是校验后的计划，每步带状态与 run_id，前端据此渲染步骤卡片
        plan=steps,
        status=status,
        phase=phase,
        public_summary=reply,
        plan_version=1 if steps else 0,
        checkpoint_thread_id=None,
        error=error,
        runtime_config_version_id=runtime_version_id,
    )
    session.add(turn)
    await session.commit()
    await session.refresh(turn)

    if turn.status is RunStatus.RUNNING:
        await _advance(session, turn)
    return turn


async def _pin_selection(
    session: AsyncSession, record: EditSession, steps: list[dict]
) -> list[dict]:
    """把当轮选区钉进每个需要遮罩的步骤。

    清除选区与修订号递增都发生在第一步之后，显式 id 才能让后续步骤共用同一块区域。
    """
    stored = await selections.get(record.id, record.revision)
    mask_asset_id = (stored or {}).get("mask_asset_id")
    if not mask_asset_id:
        return steps
    for step in steps:
        params = step["params"]
        if _wants_mask(step["tool"]) and not params.get("mask_asset_id"):
            step["params"] = {**params, "mask_asset_id": mask_asset_id}
    return steps


def _wants_mask(tool: str) -> bool:
    return "mask_asset_id" in spec_of(tool).params.model_fields


async def confirm(session: AsyncSession, record: EditSession, turn_id: uuid.UUID) -> AgentRun:
    """用户点了「执行计划」：把停在待确认的步骤放行，继续推进整轮。"""

    turn = await _get(session, record, turn_id)
    steps = _copy(turn.plan)
    waiting = [step for step in steps if step["status"] == plan_mod.WAITING]
    if turn.status is not RunStatus.QUEUED and not waiting:
        raise CannotConfirm

    # 确认时先核对整份计划的额度，不能执行到一半才发现不够
    pending_units = sum(
        spec_of(step["tool"]).quota_units(step.get("params") or {})
        for step in steps
        if step["status"] in {plan_mod.PENDING, plan_mod.WAITING}
    )
    await quota.ensure_available(session, turn.user_id, pending_units)

    for step in waiting:
        step["status"] = plan_mod.PENDING
        # 记一次批准：这一轮里同类工具后续不再重复问
        step["approved"] = True
    turn.plan = steps
    turn.status = RunStatus.RUNNING
    turn.phase = AgentPhase.EXECUTING
    _touch(turn)
    await session.commit()
    return await _advance(session, turn)


async def cancel(session: AsyncSession, record: EditSession, turn_id: uuid.UUID) -> AgentRun:
    """取消整轮：没开跑的步骤标成已取消，排队中的 run 一并结掉。"""

    turn = await _get(session, record, turn_id)
    if turn.status.is_terminal:
        raise CannotCancel
    turn.plan = plan_mod.cancel_remaining(_copy(turn.plan))
    await _cancel_queued_runs(session, turn.plan)
    _touch(turn)
    turn.status = RunStatus(plan_mod.settle(turn.plan))
    _apply_phase(turn, turn.plan)
    await turn_events.commit_and_publish(
        session, turn, "turn.updated", {"turn": await turn_events.snapshot(turn)}
    )
    await session.refresh(turn)
    return turn


async def retry(session: AsyncSession, record: EditSession, turn_id: uuid.UUID) -> AgentRun:
    """只重跑最后一个失败步骤，前面的成果不浪费。

    规划阶段就失败时没有步骤可重试，改走重新整理：保留用户原话，重新规划同一轮。
    """

    turn = await _get(session, record, turn_id)
    steps = _copy(turn.plan)
    failed = next((step for step in reversed(steps) if step["status"] == plan_mod.FAILED), None)
    if failed is None:
        if not turn.error:
            raise CannotRetry
        return await _replan(session, turn)
    failed["run_id"] = None
    failed["status"] = plan_mod.PENDING
    # 换一个尝试号：重试是新的执行，旧任务的迟到回调不能算到新预占上
    failed["attempt"] = int(failed.get("attempt", 1)) + 1
    turn.plan = steps
    turn.status = RunStatus.RUNNING
    turn.phase = AgentPhase.EXECUTING
    turn.error = None
    _touch(turn)
    await session.commit()
    return await _advance(session, turn)


async def _replan(session: AsyncSession, turn: AgentRun) -> AgentRun:
    """规划失败的轮次放回 planning，用同一句原话再整理一次。

    不新建轮次：新建会让用户那句话在对话里出现两次，也丢掉原来的位置。
    """

    turn.plan = []
    turn.plan_draft = []
    turn.reply = ""
    turn.error = None
    turn.status = RunStatus.QUEUED
    turn.phase = AgentPhase.PLANNING
    turn.public_summary = "正在安排…"
    turn.planning_attempt = (turn.planning_attempt or 1) + 1
    # 换新线程：旧 checkpoint 里可能还留着导致失败的那份计划
    turn.checkpoint_thread_id = f"turn:{turn.id}:{turn.planning_attempt}"
    turn.planning_lease_until = None
    _touch(turn)

    await session.commit()
    await session.refresh(turn)
    await turn_events.emit(
        session, turn, "planning.started", {"at": datetime.now(UTC).isoformat()}
    )
    try:
        await enqueue(PLAN_TASK, turn.id)
    except Exception:  # pragma: no cover - 队列故障不丢轮次，交恢复扫描/刷新重投
        logger.exception("规划任务投递失败 turn_id=%s", turn.id)
    return turn


async def continue_plan(session: AsyncSession, run: ToolRun) -> None:
    """某一步结束后推进后续依赖，刷新后也能从已落库的计划接着跑。

    计划即断点：步骤状态每落一步就写库，worker 重启或用户切走再回来，
    都能按库里的进度继续，而不是整轮重跑或卡住。
    """

    if run.session_id is None:
        return
    turn = await _turn_of_run(session, run)
    if turn is None:
        return

    steps = _copy(turn.plan)
    # 只有计划里已登记这个 run 才推进。同步工具在 submit 返回前就执行完，
    # 此时 run_id 还没写回计划；不校验就会「提交 → 执行 → 推进 → 再提交」死循环。
    if not any(step.get("run_id") == str(run.id) for step in steps):
        return
    for step in steps:
        if step.get("run_id") == str(run.id):
            step["status"] = run.status.value
    turn.plan = steps
    _touch(turn)
    # 先不落库：同步的下一步（如翻转）跟这次一起提交，前端不会捞到「上一步完了、下一步还没开始」
    await _advance(session, turn)


async def turns_of(session: AsyncSession, record: EditSession, limit: int = 50) -> list[AgentRun]:
    """按时间顺序取最近的对话记录，默认 50 条，供聊天区回填。"""

    result = await session.scalars(
        select(AgentRun)
        .where(AgentRun.session_id == record.id)
        .order_by(AgentRun.created_at)
        .limit(limit)
    )
    return list(result)


async def _advance(session: AsyncSession, turn: AgentRun) -> AgentRun:
    """反复下发「依赖已满足」的步骤，直到没有可推进的为止。

    画布类工具当场就成功，循环会立刻带出下一步；像素类工具入队后状态还是
    queued，本轮先停在这里，等 worker 跑完回调 continue_plan 再推进。
    """

    steps = _copy(turn.plan)
    progressed = True
    while progressed:
        progressed = False
        for step in plan_mod.ready(steps):
            if spec_of(step["tool"]).needs_approval and not step.get("approved"):
                # 需要用户点头的工具（花钱调模型的那类）不擅自执行
                step["status"] = plan_mod.WAITING
                continue
            attempt = int(step.get("attempt", 1))
            # 先认领已有的任务：崩溃后计划没写回 run_id 时不重复执行
            existing = await _run_of_step(session, turn.id, step["id"], attempt)
            if existing is None:
                latest = await _latest_run_of_step(session, turn.id, step["id"])
                if latest is not None:
                    attempt = latest.attempt + 1
                    step["attempt"] = attempt
                    existing = await _run_of_step(session, turn.id, step["id"], attempt)
            if existing is not None:
                step["run_id"] = str(existing.id)
                step["status"] = existing.status.value
                if existing.status == RunStatus.SUCCEEDED:
                    progressed = True
                continue
            try:
                run = await tools.submit(
                    session,
                    turn.user_id,
                    step["tool"],
                    step["params"],
                    turn.session_id,
                    runtime_config_version_id=turn.runtime_config_version_id,
                    turn_id=turn.id,
                    step_id=step["id"],
                    attempt=attempt,
                )
            except quota.QuotaExhausted as exc:
                step["status"] = plan_mod.FAILED
                turn.error = (
                    f"今日免费次数不足：还需 {exc.required} 次，当前可用 {exc.available} 次。"
                )
                turn.plan = steps
                turn.status = RunStatus.FAILED
                turn.phase = AgentPhase.FAILED
                _touch(turn)
                await turn_events.commit_and_publish(
                    session, turn, "turn.updated", {"turn": await turn_events.snapshot(turn)}
                )
                return turn
            step["run_id"] = str(run.id)
            step["status"] = run.status.value
            turn.plan = steps
            turn.status = RunStatus.RUNNING
            _touch(turn)
            await session.commit()
            progressed = run.status is RunStatus.SUCCEEDED

    turn.plan = steps
    turn.status = RunStatus(plan_mod.settle(steps))
    waiting = any(step["status"] == plan_mod.WAITING for step in steps)
    if turn.status is RunStatus.QUEUED and waiting:
        turn.reply = turn.reply or "下一步需要确认后再执行。"
    turn.planning_lease_until = None
    _apply_phase(turn, steps)
    _touch(turn)
    await turn_events.commit_and_publish(
        session, turn, "turn.updated", {"turn": await turn_events.snapshot(turn)}
    )
    await session.refresh(turn)
    return turn


async def _cancel_queued_runs(session: AsyncSession, steps: list[dict]) -> None:
    """把还排在队列里的 run 结掉，避免 worker 之后又去执行已取消的步骤。"""

    for step in steps:
        if not step.get("run_id") or step["status"] != plan_mod.QUEUED:
            continue
        run = await session.get(ToolRun, uuid.UUID(step["run_id"]))
        if run is None or run.status is not RunStatus.QUEUED:
            continue
        # 取消未发送的任务必须释放预占，不能让额度一直挂着
        await quota.release_run(session, run.id, reason="任务已取消")
        await runs.finish(session, run, status=RunStatus.CANCELED, error="已取消")
        step["status"] = plan_mod.CANCELED


async def _get(session: AsyncSession, record: EditSession, turn_id: uuid.UUID) -> AgentRun:
    turn = await session.scalar(
        select(AgentRun).where(AgentRun.id == turn_id, AgentRun.session_id == record.id)
    )
    if turn is None:
        raise TurnNotFound
    return turn


async def _run_of_step(
    session: AsyncSession, turn_id: uuid.UUID, step_id: str, attempt: int
) -> ToolRun | None:
    """按轮次、步骤与尝试号找已有的工具任务。"""

    return await session.scalar(
        select(ToolRun)
        .where(
            ToolRun.turn_id == turn_id,
            ToolRun.step_id == step_id,
            ToolRun.attempt == attempt,
        )
        .order_by(ToolRun.created_at.desc())
        .limit(1)
    )


async def _latest_run_of_step(
    session: AsyncSession, turn_id: uuid.UUID, step_id: str
) -> ToolRun | None:
    return await session.scalar(
        select(ToolRun)
        .where(ToolRun.turn_id == turn_id, ToolRun.step_id == step_id)
        .order_by(ToolRun.attempt.desc())
        .limit(1)
    )


async def resume_execution(session: AsyncSession, turn_id: uuid.UUID) -> AgentRun | None:
    """恢复扫描用：把卡住的 executing 轮次重新推进一步。

    先抢租约，保证多实例只有一个在推进；已经跑完的步骤直接对齐终态，
    还在跑的步骤不重复下发。
    """

    turn = await session.get(AgentRun, turn_id)
    if turn is None or turn.phase != AgentPhase.EXECUTING:
        return turn

    now = datetime.now(UTC)
    lease = timedelta(seconds=max(30, get_settings().agent_plan_lease_seconds))
    claimed = await session.execute(
        update(AgentRun)
        .where(
            AgentRun.id == turn_id,
            AgentRun.phase == AgentPhase.EXECUTING,
            or_(
                AgentRun.planning_lease_until.is_(None),
                AgentRun.planning_lease_until < now,
            ),
        )
        .values(planning_lease_until=now + lease)
        .returning(AgentRun.id)
    )
    if claimed.first() is None:
        return turn
    await session.commit()
    turn = await session.get(AgentRun, turn_id)
    if turn is None:
        return None
    return await _advance(session, turn)


async def _turn_of_run(session: AsyncSession, run: ToolRun) -> AgentRun | None:
    """反查一个 ToolRun 属于哪轮计划。优先用显式关联，老任务才退回扫描。"""

    if run.turn_id is not None:
        turn = await session.get(AgentRun, run.turn_id)
        if turn is not None and turn.session_id == run.session_id:
            return turn

    turns = await session.scalars(
        select(AgentRun)
        .where(AgentRun.session_id == run.session_id)
        .order_by(AgentRun.created_at.desc())
        .limit(20)
    )
    run_id = str(run.id)
    for turn in turns:
        if any(step.get("run_id") == run_id for step in turn.plan):
            return turn
    return None


def _copy(steps: list) -> list[dict]:
    """浅拷贝一份步骤列表。JSONB 列要整体重新赋值才会被标记为已修改。"""

    return [dict(step) for step in steps]


def _touch(turn: AgentRun) -> None:
    """显式标记 plan 已改动。原地改字典内容 SQLAlchemy 察觉不到。"""

    flag_modified(turn, "plan")

