import logging
import uuid

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.layers import LayerDocument
from app.models import Asset, ToolRun
from app.models.tool_run import RunStatus
from app.providers import ProviderError
from app.queue import enqueue
from app.services import assets, runs, sessions
from app.tools import UnknownTool, spec_of
from app.tools.context import ToolError

# 入队的任务名，worker 按这个名字接活
TASK = "run_tool"

logger = logging.getLogger(__name__)


class InvalidParams(Exception):
    """工具参数校验失败。

    与 context.py 的 ToolError 是一对，区别在于抛出的时机：
    这个在请求进来时就抛，HTTP 层直接退回，不会建 ToolRun；
    ToolError 是执行期失败，已经在跑了，只能记进 run.error。
    """


def validate(tool: str, params: dict) -> dict:
    """按工具自己的模型校验参数，界面与 Agent 走同一套规则。

    校验用的 spec.params 就是 app/tools/ 下那个入参模型，同一份定义，
    所以不会出现「界面能过、模型调用过不了」。

    通过后立刻 model_dump 成 dict 存进 ToolRun：handler 拿到的就是这份 dict，
    不用再校验一遍。失败时只取第一条错，转成人话报出去。
    """
    spec = spec_of(tool)
    try:
        return spec.params.model_validate(params).model_dump(mode="json")
    except ValidationError as exc:
        raise InvalidParams(_first_error(exc)) from exc


async def submit(
    session: AsyncSession,
    user_id: uuid.UUID,
    tool: str,
    params: dict,
    session_id: uuid.UUID | None = None,
) -> ToolRun:
    """校验参数并投递执行：画布工具当场执行，像素工具入队。

    对外唯一入口，界面点击和 Agent 调用都走这里。session_id 可空是因为
    生图类工具不需要画布；需要画布的工具在下面第一道就拦掉了。

    返回的 ToolRun 已带上终态：画布工具当场跑完才返回，像素工具返回时
    还在排队，前端拿它的 id 去订阅 SSE 进度。
    """
    spec = spec_of(tool)
    # 投递前的前置检查。执行期还有一道兜底，见 tools/context.py 的 require_session
    if spec.session_required and session_id is None:
        raise InvalidParams("此工具需要在编辑会话中使用")

    # 创建 ToolRun 记录，用来任务跟踪进度、失败原因、耗时统计、历史列表
    run = await runs.create(session, user_id, tool, validate(tool, params), session_id)
    if spec.queued:
        # 像素类工具：耗时从秒到分钟，不能占着 HTTP 请求干等，入队交给 worker
        # ← 只把 id 塞进队列
        # 入队的只有 run.id。worker 在队列里拿到这个 id，用 runs.load() 从数据库把整条记录读回来，才知道该跑什么工具
        await enqueue(TASK, run.id)
    else:
        # 画布类工具：只改文档里的数字，毫秒级，当场跑完
        await execute(session, run)
        await session.refresh(run)
    return run


async def execute(session: AsyncSession, run: ToolRun) -> None:
    """统一的执行外壳：状态流转与失败兜底集中在此，具体工具只返回结果。

    两条进入路径都汇到这里：submit() 的当场执行，和 worker 取出 run 后的执行，
    所以状态流转、错误处理只有这一份实现。

    工具自己只写业务——调用 handler 拿一个结果字典就结束，不碰落库、
    不碰撤销历史、不碰进度，全在这里统一安排。
    """
    try:
        spec = spec_of(run.tool)
        # start 之后才能报进度；每个关键节点 handler 调 runs.report()，前端进度条就是这么动的
        await runs.start(session, run)
        result = await spec.handler(session, run)
        await _record(session, run, result)
    except (ProviderError, UnknownTool, ToolError) as exc:
        # 预期内的失败：这些异常的信息本身就是给人看的，直接原样写进 run.error
        await runs.finish(session, run, status=RunStatus.FAILED, error=str(exc))
    except Exception:
        # 意料之外的异常：细节记日志，不回给前端，避免泄露堆栈或内部信息
        logger.exception("工具执行异常 tool=%s run_id=%s", run.tool, run.id)
        await session.rollback()
        await runs.finish(session, run, status=RunStatus.FAILED, error="执行失败，请重试")
    else:
        await runs.finish(session, run, status=RunStatus.SUCCEEDED, result=result)


async def _record(session: AsyncSession, run: ToolRun, result: dict) -> None:
    """把工具产物并入会话：改文档/切换当前图走 apply_edit，只产出则进图片墙。

    按返回值的内容自动分流，这是工具与落库之间的全部约定——工具不知道
    apply_edit 的存在，只是按约定返回某个 key，这里就认这个 key 记账。

      {"document": ...}                 画布类工具，只改数字
      {"asset_ids", "adopt_asset_id"}   像素类工具，顺带把新图切成当前显示
      {"asset_ids"}                     生图类工具，只产出，采用与否交给用户

    两种都会写 EditHistory（也就是都能撤销），但只有前两种改动画布。
    """
    # 生图类工具本来就没有会话，直接结束，不影响它已落库的素材
    if run.session_id is None:
        return

    try:
        record = await sessions.load(session, run.session_id)
    except sessions.SessionNotFound:
        # 排队期间会话被删了，任务本身照常记成功，只是没东西可并入
        return

    produced = await _assets(session, run.user_id, result.get("asset_ids", []))
    # adopt_asset_id 是工具点名要采用的那张，在产出的素材里找回来
    adopt_id = result.get("adopt_asset_id")
    current = next((asset for asset in produced if str(asset.id) == adopt_id), None)
    # 画布工具交回的是 JSON dict，转成对象再交回 sessions，顺带再校验一次
    raw_document = result.get("document")
    document = LayerDocument.model_validate(raw_document) if raw_document else None

    # 改了画布或换了当前图 —— 这是一次真正的编辑，要记快照
    if document is not None or current is not None:
        await sessions.apply_edit(
            session,
            record,
            run.tool,
            params=run.params,
            document=document,
            current=current,
            extra_assets=produced,
            result=result,
        )
        return

    # 只产出、没采用：进图片墙等用户点，不动当前画布
    if produced:
        await sessions.record_result(session, record, produced, run.tool, run.params, result)


async def _assets(session: AsyncSession, user_id: uuid.UUID, ids: list) -> list[Asset]:
    """把工具交回的素材 id 串查成 Asset 对象。

    逐个过 get_for_user 是为了校验归属：id 来自工具返回值，
    拿它去读别的用户的素材就越权了。取不到的直接跳过，不让单个坏 id 毁掉整次执行。
    """

    result: list[Asset] = []
    for raw in ids:
        asset = await assets.get_for_user(session, user_id, uuid.UUID(raw))
        if asset is not None:
            result.append(asset)
    return result


def _first_error(exc: ValidationError) -> str:
    """把 Pydantic 的报错转成能直接展示的一句话。

    errors()[0] 的 loc 是出错位置，嵌套模型时是 ("rect", "width") 这种，
    拼成点号路径，前端就能指出到底是哪个框没填对。
    """

    error = exc.errors()[0]
    field = ".".join(str(part) for part in error["loc"]) or "参数"
    return f"{field}：{error['msg']}"