"""免费会员每日额度服务。

所有写方法都在调用方事务内执行，不自行 commit。
余额判断只走数据库条件更新，禁止「先读余额、Python 减法、再覆盖」。
"""

import logging
import time
import uuid
from datetime import UTC, date, datetime, time as clock_time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import (
    LedgerAction,
    MembershipPolicyVersion,
    MembershipType,
    QuotaBucket,
    QuotaLedger,
    QuotaReservation,
    ReservationStatus,
)
from app.tools import spec_of

logger = logging.getLogger(__name__)

FREE = MembershipType.FREE


class QuotaError(Exception):
    """额度域错误基类。"""


class QuotaExhausted(QuotaError):
    def __init__(self, *, available: int, required: int, reset_at: datetime) -> None:
        super().__init__("今日免费次数已用完")
        self.available = available
        self.required = required
        self.reset_at = reset_at


class QuotaPolicyConflict(QuotaError):
    """同一生效日期已经存在策略版本。"""


class QuotaAdjustmentRejected(QuotaError):
    """调整会使可用次数为负。"""


def timezone() -> ZoneInfo:
    return ZoneInfo(get_settings().quota_timezone)


def today() -> date:
    """按权益时区取自然日，不读宿主机本地时区。"""
    return datetime.now(timezone()).date()


def reset_at(quota_date: date) -> datetime:
    """该日额度桶的重置时刻：次日 00:00（权益时区），返回 UTC。"""
    next_day = quota_date + timedelta(days=1)
    local = datetime.combine(next_day, clock_time.min, tzinfo=timezone())
    return local.astimezone(UTC)


def units_for(tool: str, params: dict) -> int:
    """按工具注册表计算本次提交的 AI 图片次数。"""
    return spec_of(tool).quota_units(params or {})


async def active_policy(
    session: AsyncSession, quota_date: date | None = None
) -> MembershipPolicyVersion:
    day = quota_date or today()
    policy = await session.scalar(
        select(MembershipPolicyVersion)
        .where(
            MembershipPolicyVersion.member_type == FREE,
            MembershipPolicyVersion.effective_from <= day,
        )
        .order_by(
            MembershipPolicyVersion.effective_from.desc(),
            MembershipPolicyVersion.version_seq.desc(),
        )
        .limit(1)
    )
    if policy is not None:
        return policy
    return await _seed_default_policy(session, day)


async def _seed_default_policy(
    session: AsyncSession, quota_date: date
) -> MembershipPolicyVersion:
    """迁移未执行或测试库为空时的兜底；生产以迁移种子/后台发布为准。"""
    settings = get_settings()
    seq = (
        await session.scalar(
            select(func.max(MembershipPolicyVersion.version_seq)).where(
                MembershipPolicyVersion.member_type == FREE
            )
        )
        or 0
    ) + 1
    await session.execute(
        pg_insert(MembershipPolicyVersion)
        .values(
            member_type=FREE,
            version_seq=seq,
            daily_limit=max(0, settings.free_daily_limit),
            counting_unit="image",
            timezone=settings.quota_timezone,
            features={"vip": "coming_soon"},
            effective_from=quota_date,
            published_by=None,
            note="运行时兜底：免费会员默认策略",
        )
        .on_conflict_do_nothing(index_elements=["member_type", "effective_from"])
    )
    await session.flush()
    policy = await session.scalar(
        select(MembershipPolicyVersion)
        .where(
            MembershipPolicyVersion.member_type == FREE,
            MembershipPolicyVersion.effective_from <= quota_date,
        )
        .order_by(MembershipPolicyVersion.effective_from.desc())
        .limit(1)
    )
    if policy is None:  # pragma: no cover - 唯一约束 + 上面的插入保证能查到
        raise QuotaError("无法解析免费会员策略")
    return policy


async def _bucket(
    session: AsyncSession, user_id: uuid.UUID, quota_date: date
) -> QuotaBucket | None:
    return await session.scalar(
        select(QuotaBucket).where(
            QuotaBucket.user_id == user_id, QuotaBucket.quota_date == quota_date
        )
    )


async def _ensure_bucket(
    session: AsyncSession, user_id: uuid.UUID, quota_date: date
) -> QuotaBucket:
    bucket = await _bucket(session, user_id, quota_date)
    if bucket is not None:
        return bucket

    policy = await active_policy(session, quota_date)
    # 并发首次使用：唯一约束兜底，冲突方改为读取已创建的行
    await session.execute(
        pg_insert(QuotaBucket)
        .values(
            user_id=user_id,
            quota_date=quota_date,
            policy_version_id=policy.id,
            limit=policy.daily_limit,
            adjustment=0,
            reserved=0,
            consumed=0,
        )
        .on_conflict_do_nothing(index_elements=["user_id", "quota_date"])
    )
    await session.flush()
    bucket = await _bucket(session, user_id, quota_date)
    if bucket is None:  # pragma: no cover
        raise QuotaError("无法创建额度桶")
    return bucket


async def _available(session: AsyncSession, bucket_id: uuid.UUID) -> int:
    value = await session.scalar(
        select(
            QuotaBucket.limit
            + QuotaBucket.adjustment
            - QuotaBucket.reserved
            - QuotaBucket.consumed
        ).where(QuotaBucket.id == bucket_id)
    )
    return int(value or 0)


def _ledger(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    bucket_id: uuid.UUID,
    action: LedgerAction,
    units: int,
    available_after: int,
    reservation_id: uuid.UUID | None = None,
    operator_id: uuid.UUID | None = None,
    reason: str | None = None,
    idempotency_key: str | None = None,
) -> QuotaLedger:
    entry = QuotaLedger(
        user_id=user_id,
        bucket_id=bucket_id,
        reservation_id=reservation_id,
        action=action,
        units=units,
        available_after=available_after,
        operator_id=operator_id,
        reason=reason,
        idempotency_key=idempotency_key,
    )
    session.add(entry)
    return entry


async def reserve(
    session: AsyncSession,
    user_id: uuid.UUID,
    units: int,
    *,
    logical_key: str,
    run_id: uuid.UUID | None = None,
    turn_id: uuid.UUID | None = None,
    step_id: str | None = None,
    quota_date: date | None = None,
) -> QuotaReservation | None:
    """预占一次逻辑消费单元。

    返回 None 表示该工具不消耗次数。相同 logical_key 已存在且未释放时直接返回，
    保证网络重试、ARQ 重投、Agent 恢复不会重复预占。
    """

    if units <= 0:
        return None

    existing = await session.scalar(
        select(QuotaReservation).where(
            QuotaReservation.user_id == user_id,
            QuotaReservation.logical_key == logical_key,
        )
    )
    if existing is not None:
        if existing.status is ReservationStatus.RELEASED:
            # 已释放的逻辑单元必须换新键重试，旧代数的迟到回调不能结算新预占
            raise QuotaError("该请求的额度已释放，请重新发起")
        return existing

    day = quota_date or today()
    bucket = await _ensure_bucket(session, user_id, day)
    policy = await active_policy(session, day)
    settings = get_settings()

    reservation = QuotaReservation(
        user_id=user_id,
        bucket_id=bucket.id,
        policy_version_id=policy.id,
        logical_key=logical_key,
        units=units,
        run_id=run_id,
        turn_id=turn_id,
        step_id=step_id,
        status=ReservationStatus.RESERVED,
    )
    session.add(reservation)
    try:
        async with session.begin_nested():
            await session.flush()
    except IntegrityError:
        # 并发同键：对方已插入，本次不再占额度
        found = await session.scalar(
            select(QuotaReservation).where(
                QuotaReservation.user_id == user_id,
                QuotaReservation.logical_key == logical_key,
            )
        )
        if found is not None:
            return found
        raise

    if settings.quota_enforce:
        changed = await session.execute(
            update(QuotaBucket)
            .where(
                QuotaBucket.id == bucket.id,
                QuotaBucket.limit
                + QuotaBucket.adjustment
                - QuotaBucket.reserved
                - QuotaBucket.consumed
                >= units,
            )
            .values(reserved=QuotaBucket.reserved + units)
            .returning(QuotaBucket.id)
        )
        if changed.first() is None:
            available = await _available(session, bucket.id)
            raise QuotaExhausted(
                available=max(0, available), required=units, reset_at=reset_at(day)
            )
    else:
        # shadow：仍记录预占与流水，用于核对真实调用链，但不拦截提交
        await session.execute(
            update(QuotaBucket)
            .where(QuotaBucket.id == bucket.id)
            .values(reserved=QuotaBucket.reserved + units)
        )

    available_after = await _available(session, bucket.id)
    _ledger(
        session,
        user_id=user_id,
        bucket_id=bucket.id,
        reservation_id=reservation.id,
        action=LedgerAction.RESERVE,
        units=units,
        available_after=available_after,
        idempotency_key=f"reserve:{user_id}:{logical_key}",
    )
    await session.flush()
    return reservation


async def settle_run(
    session: AsyncSession,
    run_id: uuid.UUID,
    delivered: int,
    *,
    reason: str | None = None,
) -> QuotaReservation | None:
    """按 run 找到预占后结算。"""
    reservation = await _reservation_of_run(session, run_id)
    return await settle(session, reservation, delivered, reason=reason)


async def settle(
    session: AsyncSession,
    reservation: QuotaReservation | None,
    delivered: int,
    *,
    reason: str | None = None,
) -> QuotaReservation | None:
    """按成功交付张数结算。多预占的部分释放，重复调用不重复扣减。"""

    if reservation is None or reservation.status in {
        ReservationStatus.SETTLED,
        ReservationStatus.RELEASED,
    }:
        return reservation

    units = reservation.units
    settled = max(0, min(units, int(delivered)))
    released = units - settled

    changed = await session.execute(
        update(QuotaBucket)
        .where(
            QuotaBucket.id == reservation.bucket_id,
            QuotaBucket.reserved >= units,
        )
        .values(
            reserved=QuotaBucket.reserved - units,
            consumed=QuotaBucket.consumed + settled,
        )
        .returning(QuotaBucket.id)
    )
    if changed.first() is None:
        logger.warning("额度结算时桶预占不足 reservation=%s", reservation.id)
        return reservation

    reservation.settled = settled
    reservation.released = released
    reservation.status = ReservationStatus.SETTLED

    available_after = await _available(session, reservation.bucket_id)
    if settled:
        _ledger(
            session,
            user_id=reservation.user_id,
            bucket_id=reservation.bucket_id,
            reservation_id=reservation.id,
            action=LedgerAction.CONSUME,
            units=settled,
            available_after=available_after,
            reason=reason,
            idempotency_key=f"consume:{reservation.id}",
        )
    if released:
        _ledger(
            session,
            user_id=reservation.user_id,
            bucket_id=reservation.bucket_id,
            reservation_id=reservation.id,
            action=LedgerAction.RELEASE,
            units=released,
            available_after=available_after,
            reason=reason or "成功交付少于预占",
            idempotency_key=f"release:{reservation.id}",
        )
    await session.flush()
    return reservation


async def release_run(
    session: AsyncSession, run_id: uuid.UUID, *, reason: str | None = None
) -> QuotaReservation | None:
    """失败或未发送取消时全额释放。"""
    reservation = await _reservation_of_run(session, run_id)
    return await release(session, reservation, reason=reason)


async def release(
    session: AsyncSession,
    reservation: QuotaReservation | None,
    *,
    reason: str | None = None,
) -> QuotaReservation | None:
    """失败或未发送取消时全额释放。重复调用幂等。"""

    if reservation is None or reservation.status in {
        ReservationStatus.SETTLED,
        ReservationStatus.RELEASED,
    }:
        return reservation

    units = reservation.units
    changed = await session.execute(
        update(QuotaBucket)
        .where(
            QuotaBucket.id == reservation.bucket_id,
            QuotaBucket.reserved >= units,
        )
        .values(reserved=QuotaBucket.reserved - units)
        .returning(QuotaBucket.id)
    )
    if changed.first() is None:
        logger.warning("额度释放时桶预占不足 reservation=%s", reservation.id)
        return reservation

    reservation.released = units
    reservation.status = ReservationStatus.RELEASED
    available_after = await _available(session, reservation.bucket_id)
    _ledger(
        session,
        user_id=reservation.user_id,
        bucket_id=reservation.bucket_id,
        reservation_id=reservation.id,
        action=LedgerAction.RELEASE,
        units=units,
        available_after=available_after,
        reason=reason or "任务失败释放",
        idempotency_key=f"release:{reservation.id}",
    )
    await session.flush()
    return reservation


async def release_reservation(
    session: AsyncSession,
    reservation_id: uuid.UUID,
    *,
    operator_id: uuid.UUID,
    reason: str,
) -> QuotaReservation | None:
    """管理员释放异常预占。必须填写原因，释放动作本身写入流水。"""

    reservation = await session.get(QuotaReservation, reservation_id)
    if reservation is None:
        return None
    return await release(
        session, reservation, reason=f"{reason}（管理员 {operator_id}）"
    )


async def mark_unknown(
    session: AsyncSession, run_id: uuid.UUID, *, reason: str = "外部调用结果未知"
) -> QuotaReservation | None:
    """外部请求已发出但结果未知：保留预占，进入人工核查，不自动重发。"""

    reservation = await _reservation_of_run(session, run_id)
    if reservation is None or reservation.status is not ReservationStatus.RESERVED:
        return reservation
    minutes = max(1, get_settings().quota_unknown_minutes)
    reservation.status = ReservationStatus.UNKNOWN
    reservation.expires_at = datetime.now(UTC) + timedelta(minutes=minutes)
    await session.flush()
    logger.warning(
        "额度预占进入未知状态 reservation=%s run=%s reason=%s",
        reservation.id,
        run_id,
        reason,
    )
    return reservation


async def _reservation_of_run(
    session: AsyncSession, run_id: uuid.UUID
) -> QuotaReservation | None:
    return await session.scalar(
        select(QuotaReservation).where(QuotaReservation.run_id == run_id)
    )


async def snapshot(session: AsyncSession, user_id: uuid.UUID) -> dict:
    """用户当天权益快照。没有日桶时按当前策略合成，不产生写操作。"""

    day = today()
    policy = await active_policy(session, day)
    bucket = await _bucket(session, user_id, day)
    if bucket is None:
        limit = policy.daily_limit
        adjustment = reserved = consumed = 0
    else:
        limit = bucket.limit
        adjustment = bucket.adjustment
        reserved = bucket.reserved
        consumed = bucket.consumed

    available = limit + adjustment - reserved - consumed
    return {
        "membership_type": MembershipType.FREE.value,
        "display_name": "免费会员",
        "quota_date": day,
        "daily_limit": limit,
        "adjustment": adjustment,
        "reserved": reserved,
        "consumed": consumed,
        "available": max(0, available),
        "counting_unit": policy.counting_unit,
        "timezone": policy.timezone,
        "reset_at": reset_at(day),
        "policy_version_id": policy.id,
        "policy_version_seq": policy.version_seq,
        "vip": {"status": "coming_soon", "display_name": "VIP 会员", "message": "更多权益即将开放"},
    }


async def ensure_available(
    session: AsyncSession, user_id: uuid.UUID, units: int
) -> None:
    """确认前一次性核对整份计划的额度，避免执行到一半才发现不够。"""

    if units <= 0:
        return
    data = await snapshot(session, user_id)
    if data["available"] < units:
        raise QuotaExhausted(
            available=data["available"], required=units, reset_at=data["reset_at"]
        )


async def estimate(user_id: uuid.UUID, tool: str, params: dict) -> dict:
    """只估算不预占。正式提交时会重新校验余额。"""

    units = units_for(tool, params)
    return {"required": units, "tool": tool}


async def ledger_page(
    session: AsyncSession, user_id: uuid.UUID, *, limit: int = 50, offset: int = 0
) -> tuple[list[QuotaLedger], int]:
    total = await session.scalar(
        select(func.count()).select_from(QuotaLedger).where(QuotaLedger.user_id == user_id)
    )
    rows = await session.scalars(
        select(QuotaLedger)
        .where(QuotaLedger.user_id == user_id)
        .order_by(QuotaLedger.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(rows), int(total or 0)


async def list_policies(session: AsyncSession) -> list[MembershipPolicyVersion]:
    return list(
        await session.scalars(
            select(MembershipPolicyVersion)
            .where(MembershipPolicyVersion.member_type == FREE)
            .order_by(
                MembershipPolicyVersion.effective_from.desc(),
                MembershipPolicyVersion.version_seq.desc(),
            )
        )
    )


async def publish_policy(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID | None,
    daily_limit: int,
    effective_from: date | None = None,
    note: str | None = None,
) -> MembershipPolicyVersion:
    day = effective_from or (today() + timedelta(days=1))
    if daily_limit < 0:
        raise QuotaError("每日上限不能为负")

    seq = (
        await session.scalar(
            select(func.max(MembershipPolicyVersion.version_seq)).where(
                MembershipPolicyVersion.member_type == FREE
            )
        )
        or 0
    ) + 1
    policy = MembershipPolicyVersion(
        member_type=FREE,
        version_seq=seq,
        daily_limit=daily_limit,
        counting_unit="image",
        timezone=get_settings().quota_timezone,
        features={"vip": "coming_soon"},
        effective_from=day,
        published_by=actor_id,
        note=note,
    )
    session.add(policy)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise QuotaPolicyConflict("该生效日期已有策略版本") from exc
    return policy


async def user_quota(
    session: AsyncSession, user_id: uuid.UUID, quota_date: date | None = None
) -> dict:
    """管理端查看指定用户某天的额度与异常预占。"""

    day = quota_date or today()
    policy = await active_policy(session, day)
    bucket = await _bucket(session, user_id, day)
    reservations = list(
        await session.scalars(
            select(QuotaReservation)
            .where(
                QuotaReservation.user_id == user_id,
                QuotaReservation.status.in_(
                    [ReservationStatus.RESERVED, ReservationStatus.UNKNOWN]
                ),
            )
            .order_by(QuotaReservation.created_at.desc())
        )
    )
    limit = bucket.limit if bucket else policy.daily_limit
    adjustment = bucket.adjustment if bucket else 0
    reserved = bucket.reserved if bucket else 0
    consumed = bucket.consumed if bucket else 0
    return {
        "quota_date": day,
        "limit": limit,
        "adjustment": adjustment,
        "reserved": reserved,
        "consumed": consumed,
        "available": max(0, limit + adjustment - reserved - consumed),
        "reset_at": reset_at(day),
        "policy_version_id": policy.id,
        "policy_version_seq": policy.version_seq,
        "open_reservations": reservations,
    }


async def adjust(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    user_id: uuid.UUID,
    units: int,
    reason: str,
    quota_date: date | None = None,
) -> QuotaBucket:
    """管理员纠错：只写调整流水，不直接改 reserved/consumed。"""

    if units == 0:
        raise QuotaError("调整数量不能为 0")
    if not reason.strip():
        raise QuotaError("必须填写调整原因")

    day = quota_date or today()
    bucket = await _ensure_bucket(session, user_id, day)

    if units < 0:
        changed = await session.execute(
            update(QuotaBucket)
            .where(
                QuotaBucket.id == bucket.id,
                QuotaBucket.limit
                + QuotaBucket.adjustment
                + units
                - QuotaBucket.reserved
                - QuotaBucket.consumed
                >= 0,
            )
            .values(adjustment=QuotaBucket.adjustment + units)
            .returning(QuotaBucket.id)
        )
        if changed.first() is None:
            raise QuotaAdjustmentRejected("调整后可用次数不能为负")
    else:
        await session.execute(
            update(QuotaBucket)
            .where(QuotaBucket.id == bucket.id)
            .values(adjustment=QuotaBucket.adjustment + units)
        )

    available_after = await _available(session, bucket.id)
    _ledger(
        session,
        user_id=user_id,
        bucket_id=bucket.id,
        action=LedgerAction.ADJUST,
        units=abs(units),
        available_after=available_after,
        operator_id=actor_id,
        reason=reason.strip(),
        # 管理员可对同一天连续调整，用时间戳保证每次都是新流水
        idempotency_key=f"adjust:{bucket.id}:{time.time_ns()}",
    )
    await session.flush()
    await session.refresh(bucket)
    return bucket
