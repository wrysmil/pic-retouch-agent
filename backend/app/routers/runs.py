"""
任务执行相关接口。

提供图片生成任务的创建和查询功能。

文生图作为工具注册表中的第一个工具对外暴露：用户提交参数 →
tools.submit 校验并入队 → worker 执行统一外壳（tools.execute）→
状态经 SSE 实时推送 → 候选图转存为素材。
"""

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionDep
from app.deps import CurrentUser
from app.models.tool_run import ToolRun
from app.schemas.asset import AssetOut
from app.schemas.run import GenerateIn, RunOut
from app.services import assets as asset_service
from app.services import runs, tools
from app.services.runs import RunNotFound
from app.tools import GENERATE_IMAGE

router = APIRouter(tags=["runs"])


async def _candidates(session: AsyncSession, run: ToolRun) -> list[AssetOut]:
    """获取候选图的签名 URL（签名 URL 有有效期，每次读取时重新签发）。"""
    result = []
    for raw in run.result.get("asset_ids", []):
        asset = await asset_service.get_for_user(session, run.user_id, uuid.UUID(raw))
        if asset is not None:
            result.append(AssetOut.of(asset))
    return result


@router.post(
    "/generations",
    status_code=status.HTTP_202_ACCEPTED,
    summary="创建生成任务",
    description="提交文生图任务，异步执行后通过 SSE 推送进度。",
)
async def create_generation(
    payload: GenerateIn,
    user: CurrentUser,
    session: SessionDep,
) -> RunOut:
    """
    创建图片生成任务。

    **请求参数 (GenerateIn)**:
    - **prompt**: 图片描述文本，用于指导模型生成图片的内容（必填，1-1500 字符）
    - **ratio**: 宽高比例，如 '1:1'（正方形）、'16:9'（横向）、'9:16'（竖向），默认 1:1
    - **count**: 生成图片数量，默认 4 张（1-6 张）
    - **negative_prompt**: 负面提示词，描述不希望出现在图片中的元素（可选）
    - **seed**: 随机种子，相同种子可复现相似结果（可选，0-2147483647）
    - **reference_asset_ids**: 参考图片 ID 列表，最多 3 张，用于风格/内容参考（可选）

    **返回**: 创建的任务信息（RunOut），包含 run_id，前端可通过 SSE 订阅进度

    **流程**:
    1. 校验参考图片是否存在
    2. 创建任务记录（状态为 queued）
    3. 任务入队异步执行（统一工具执行外壳）
    4. 返回任务信息

    **可能错误**:
    - 404: 参考图片不存在

    """
    for asset_id in payload.reference_asset_ids:
        if await asset_service.get_for_user(session, user.id, asset_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "参考图不存在")

    params = payload.model_dump(mode="json")
    run = await tools.submit(session, user.id, GENERATE_IMAGE.name, params)
    return RunOut.of(run)


@router.get(
    "/runs/{run_id}",
    summary="获取任务详情",
    description="查询指定任务的执行状态和结果。",
)
async def get_run(
    run_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> RunOut:
    """
    获取任务详情。

    - **run_id**: 任务 UUID
    - **返回**: 任务详细信息，包括：
      - 状态（pending/running/completed/failed）
      - 进度百分比
      - 结果（包含候选图列表）

    **可能错误**:
    - 404: 任务不存在
    """
    try:
        run = await runs.get(session, run_id, user.id)
    except RunNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务不存在") from exc
    return RunOut.of(run, await _candidates(session, run))