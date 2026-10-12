"""多步计划的结构与状态机。

图只负责产出计划，下发与推进由 services/agent 按这里的规则驱动，
所以计划本身要能独立表达「走到哪一步、下一步谁能跑」。
"""

from app.services import tools as tool_service
from app.tools import spec_of

MAX_STEPS = 8

PENDING = "pending"
WAITING = "waiting"
QUEUED = "queued"
RUNNING = "running"
SUCCEEDED = "succeeded"
FAILED = "failed"
CANCELED = "canceled"

# 还没结束的状态，整轮计划据此判断是否仍在推进
_OPEN = {PENDING, WAITING, QUEUED, RUNNING}
# 依赖失败时，下游不再尝试
_BLOCKED = {FAILED, CANCELED}


class PlanError(Exception):
    """计划结构非法：超长、依赖悬空或成环。"""


def assemble(raw: list[dict]) -> list[dict]:
    """补全步骤 id、顺序依赖与初始状态，并拒绝超长或成环的计划。

    模型通常只给一串工具调用，不写依赖关系。缺 depends_on 时按给出顺序
    串成链，这正是「先抠图再调亮」的默认语义。
    """
    if len(raw) > MAX_STEPS:
        raise PlanError(f"计划超过 {MAX_STEPS} 步，请拆成多次说明")

    steps: list[dict] = []
    for index, item in enumerate(raw, start=1):
        step_id = item.get("id") or f"s{index}"
        depends = item.get("depends_on")
        if depends is None:
            depends = [steps[-1]["id"]] if steps else []
        steps.append(
            {
                "id": step_id,
                "tool": item["tool"],
                "params": item.get("params") or {},
                "depends_on": list(depends),
                "run_id": item.get("run_id"),
                "status": item.get("status") or PENDING,
            }
        )

    known = {step["id"] for step in steps}
    for step in steps:
        missing = [dep for dep in step["depends_on"] if dep not in known]
        if missing:
            raise PlanError(f"步骤 {step['id']} 依赖了不存在的步骤")
    if _cyclic(steps):
        raise PlanError("计划步骤存在循环依赖")
    return steps


def validate(raw: list[dict]) -> list[dict]:
    """逐步按工具入参模型校验，再补全成可执行结构。"""
    checked: list[dict] = []
    for step in raw:
        spec = spec_of(step["tool"])
        params = tool_service.validate(spec.name, step.get("params") or {})
        checked.append({**step, "tool": spec.name, "params": params})
    return assemble(checked)


def ready(steps: list[dict]) -> list[dict]:
    """本可立刻下发的步骤：自己还没跑，且依赖全部成功。"""
    by_id = {step["id"]: step for step in steps}
    return [step for step in steps if _is_ready(step, by_id)]


def settle(steps: list[dict]) -> str:
    """根据步骤状态汇总整轮计划。"""
    statuses = [step["status"] for step in steps]
    if any(status in _OPEN for status in statuses):
        # 只剩待确认的步骤：整轮停在排队，等用户点「执行计划」
        if any(status == WAITING for status in statuses) and not any(
            status in {QUEUED, RUNNING} for status in statuses
        ):
            return QUEUED
        return RUNNING
    if any(status == FAILED for status in statuses):
        return FAILED
    if any(status == CANCELED for status in statuses):
        return CANCELED
    return SUCCEEDED


def needs_confirm(steps: list[dict]) -> bool:
    """多步计划先给用户看一眼再执行；单步没必要多一次点击。"""
    return len(steps) > 1


def cancel_remaining(steps: list[dict]) -> list[dict]:
    """把还没开跑的步骤标成已取消，已在跑的不打断。"""
    return [
        {**step, "status": CANCELED} if step["status"] in {PENDING, WAITING} else step
        for step in steps
    ]


def _is_ready(step: dict, by_id: dict[str, dict]) -> bool:
    if step["status"] not in {PENDING, WAITING} or step.get("run_id"):
        return False
    deps = [by_id[dep] for dep in step["depends_on"]]
    if any(dep["status"] in _BLOCKED for dep in deps):
        return False
    return all(dep["status"] == SUCCEEDED for dep in deps)


def _cyclic(steps: list[dict]) -> bool:
    """Kahn 拓扑排序：消不完的点说明留在环里。"""
    ids = [step["id"] for step in steps]
    incoming = {step_id: 0 for step_id in ids}
    outgoing: dict[str, list[str]] = {step_id: [] for step_id in ids}
    for step in steps:
        for dep in step["depends_on"]:
            outgoing[dep].append(step["id"])
            incoming[step["id"]] += 1

    queue = [step_id for step_id, count in incoming.items() if count == 0]
    seen = 0
    while queue:
        node = queue.pop()
        seen += 1
        for nxt in outgoing[node]:
            incoming[nxt] -= 1
            if incoming[nxt] == 0:
                queue.append(nxt)
    return seen != len(ids)
