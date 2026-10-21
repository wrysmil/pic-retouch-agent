"""免费会员额度接口。

用户端只读自己的权益与流水；写操作仅管理员可用，且必须留下审计与调整流水。
"""

import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.db import SessionDep
from app.deps import AdminUser, CurrentUser
from app.models import AdminAuditLog, AuditAction, User
from app.schemas.quota import (
    AdjustmentIn,
    AdminUserQuotaOut,
    EntitlementsOut,
    EstimateIn,
    EstimateOut,
    LedgerEntryOut,
    LedgerPageOut,
    OpenReservationOut,
    PolicyCreateIn,
    PolicyOut,
    ReleaseReservationIn,
)
from app.services import quota
from app.tools import UnknownTool

router = APIRouter(tags=["quota"])


def quota_http_error(exc: quota.QuotaExhausted) -> HTTPException:
    """把超额异常转成前端可分支处理的结构化 409。"""

    return HTTPException(
        status.HTTP_409_CONFLICT,
        detail={
            "code": "QUOTA_EXHAUSTED",
            "message": "今日免费次数已用完，明日 00:00 重置",
            "available": exc.available,
            "required": exc.required,
            "reset_at": exc.reset_at.isoformat(),
        },
    )


@router.get(
    "/me/entitlements",
    response_model=EntitlementsOut,
    summary="我的会员权益与每日额度",
)
async def my_entitlements(user: CurrentUser, session: SessionDep) -> EntitlementsOut:
    data = await quota.snapshot(session, user.id)
    return EntitlementsOut(**data)


@router.post(
    "/quota/estimate",
    response_model=EstimateOut,
    summary="估算一次操作的 AI 次数",
    description="只估算不预占；正式提交时会重新校验余额与参数。",
)
async def estimate(
    payload: EstimateIn, user: CurrentUser, session: SessionDep
) -> EstimateOut:
    try:
        result = await quota.estimate(user.id, payload.tool, payload.params)
    except UnknownTool as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    data = await quota.snapshot(session, user.id)
    return EstimateOut(
        tool=payload.tool,
        required=result["required"],
        available=data["available"],
        affordable=result["required"] <= data["available"],
        reset_at=data["reset_at"],
        counting_unit=data["counting_unit"],
    )


@router.get(
    "/me/quota-ledger",
    response_model=LedgerPageOut,
    summary="我的额度流水",
)
async def my_ledger(
    user: CurrentUser,
    session: SessionDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> LedgerPageOut:
    rows, total = await quota.ledger_page(session, user.id, limit=limit, offset=offset)
    return LedgerPageOut(total=total, items=[LedgerEntryOut.of(row) for row in rows])


@router.get(
    "/admin/membership-policies",
    response_model=list[PolicyOut],
    summary="免费权益策略版本",
)
async def list_policies(_actor: AdminUser, session: SessionDep) -> list[PolicyOut]:
    return [PolicyOut.of(policy) for policy in await quota.list_policies(session)]


@router.post(
    "/admin/membership-policies",
    response_model=PolicyOut,
    status_code=status.HTTP_201_CREATED,
    summary="发布免费权益策略",
    description="默认从明日 00:00（权益时区）生效；当天修正请使用额度调整。",
)
async def publish_policy(
    payload: PolicyCreateIn, actor: AdminUser, session: SessionDep
) -> PolicyOut:
    try:
        policy = await quota.publish_policy(
            session,
            actor_id=actor.id,
            daily_limit=payload.daily_limit,
            effective_from=payload.effective_from,
            note=payload.note,
        )
    except quota.QuotaPolicyConflict as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    session.add(
        AdminAuditLog(
            actor_id=actor.id,
            action=AuditAction.MEMBERSHIP_POLICY_PUBLISHED.value,
            target_kind="membership_policy_version",
            target_id=policy.id,
            changes={
                "daily_limit": policy.daily_limit,
                "effective_from": policy.effective_from.isoformat(),
                "version_seq": policy.version_seq,
            },
        )
    )
    await session.commit()
    await session.refresh(policy)
    return PolicyOut.of(policy)


@router.get(
    "/admin/users/{user_id}/quota",
    response_model=AdminUserQuotaOut,
    summary="查看指定用户额度",
)
async def user_quota(
    user_id: uuid.UUID,
    _actor: AdminUser,
    session: SessionDep,
) -> AdminUserQuotaOut:
    if await session.get(User, user_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")
    data = await quota.user_quota(session, user_id)
    return AdminUserQuotaOut(
        **{
            **data,
            "open_reservations": [
                OpenReservationOut.of(row) for row in data["open_reservations"]
            ],
        }
    )


@router.post(
    "/admin/quota-reservations/{reservation_id}/release",
    summary="释放异常预占",
    description="仅用于结果未知或长期未结束的预占；必须填写原因并记入流水。",
)
async def release_reservation(
    reservation_id: uuid.UUID,
    payload: ReleaseReservationIn,
    actor: AdminUser,
    session: SessionDep,
) -> dict:
    reservation = await quota.release_reservation(
        session,
        reservation_id,
        operator_id=actor.id,
        reason=payload.reason.strip(),
    )
    if reservation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "预占不存在")

    session.add(
        AdminAuditLog(
            actor_id=actor.id,
            action=AuditAction.QUOTA_ADJUSTED.value,
            target_kind="quota_reservation",
            target_id=reservation.id,
            changes={"released": reservation.released, "reason": payload.reason.strip()},
        )
    )
    await session.commit()
    return {"id": str(reservation.id), "status": reservation.status.value}


@router.post(
    "/admin/users/{user_id}/quota-adjustments",
    response_model=AdminUserQuotaOut,
    summary="管理员调整额度",
    description="只写调整流水，不直接覆盖 reserved/consumed；必须填写原因。",
)
async def adjust_quota(
    user_id: uuid.UUID,
    payload: AdjustmentIn,
    actor: AdminUser,
    session: SessionDep,
) -> AdminUserQuotaOut:
    if await session.get(User, user_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")
    try:
        bucket = await quota.adjust(
            session,
            actor_id=actor.id,
            user_id=user_id,
            units=payload.units,
            reason=payload.reason,
            quota_date=payload.quota_date,
        )
    except quota.QuotaAdjustmentRejected as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except quota.QuotaError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc

    session.add(
        AdminAuditLog(
            actor_id=actor.id,
            action=AuditAction.QUOTA_ADJUSTED.value,
            target_kind="user",
            target_id=user_id,
            changes={
                "units": payload.units,
                "quota_date": bucket.quota_date.isoformat(),
                "reason": payload.reason.strip(),
            },
        )
    )
    await session.commit()

    data = await quota.user_quota(session, user_id, payload.quota_date)
    return AdminUserQuotaOut(
        **{
            **data,
            "open_reservations": [
                OpenReservationOut.of(row) for row in data["open_reservations"]
            ],
        }
    )
