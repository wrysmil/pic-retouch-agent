import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response

from app.db import SessionDep
from app.deps import CurrentUser
from app.routers.quota import quota_http_error
from app.schemas.batch import BatchIn, BatchOut
from app.schemas.run import RunOut
from app.security.rate_limit import rate_limit
from app.services import batch, quota, runs, tools
from app.services.batch import EmptyBatch, UnknownBatchAsset
from app.services.runs import RunNotFound
from app.services.tools import InvalidParams
from app.tools.batch import BATCH_NAME

router = APIRouter(prefix="/batches", tags=["batches"])


@router.post(
    "",
    dependencies=[Depends(rate_limit("ai-batch"))],
    status_code=status.HTTP_202_ACCEPTED,
    summary="提交批量处理",
    description="对多张素材执行同一套像素处理链，入队后由 worker 逐项推进并回报进度。",
)
async def create_batch(payload: BatchIn, user: CurrentUser, session: SessionDep) -> RunOut:
    try:
        await batch.require_assets(session, user.id, payload.asset_ids)
    except UnknownBatchAsset as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "素材不存在") from exc
    try:
        run = await tools.submit(session, user.id, BATCH_NAME, payload.model_dump(mode="json"))
    except InvalidParams as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    except quota.QuotaExhausted as exc:
        raise quota_http_error(exc) from exc
    return RunOut.of(run)


@router.get("", summary="批量任务列表", description="按创建时间倒序返回当前用户最近的批量任务。")
async def list_batches(
    user: CurrentUser,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[BatchOut]:
    records = await batch.list_for_user(session, user.id, limit)
    return [await batch.detail(session, record) for record in records]


@router.get(
    "/{run_id}",
    summary="批量任务详情",
    description="返回逐项处理状态与产出素材；非批量任务按不存在处理。",
)
async def get_batch(run_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> BatchOut:
    try:
        run = await runs.get(session, run_id, user.id)
    except RunNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务不存在") from exc
    if run.tool != BATCH_NAME:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务不存在")
    return await batch.detail(session, run)


@router.get(
    "/{run_id}/export",
    summary="打包批量结果",
    description="把批量任务的全部产出素材打成 ZIP 下载；尚无结果时返回 409。",
)
async def export_batch(run_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> Response:
    try:
        run = await runs.get(session, run_id, user.id)
    except RunNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务不存在") from exc
    if run.tool != BATCH_NAME:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务不存在")
    try:
        packed = await batch.pack(session, run)
    except EmptyBatch as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "还没有可打包的结果") from exc
    return Response(
        content=packed.data,
        media_type="application/zip",
        headers={"Content-Disposition": packed.disposition},
    )
