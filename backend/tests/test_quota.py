import asyncio
import uuid
from datetime import date, timedelta

import httpx
import pytest
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionFactory
from app.models import QuotaBucket, QuotaLedger, QuotaReservation, ReservationStatus, User
from app.services import quota
from app.tools.quota_units import batch_units


@pytest.fixture
def enforce():
    """默认测试是 shadow；额度用例显式打开强制拦截。"""
    settings = get_settings()
    original = settings.quota_enforce
    settings.quota_enforce = True
    yield
    settings.quota_enforce = original


async def _user() -> uuid.UUID:
    async with SessionFactory() as session:
        user = User(
            username=f"test_quota_{uuid.uuid4().hex[:10]}",
            password_hash="not-used",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user.id


async def test_partial_delivery_settles_only_what_succeeded(enforce) -> None:
    user_id = await _user()
    key = f"test:{uuid.uuid4()}"

    async with SessionFactory() as session:
        reservation = await quota.reserve(session, user_id, 4, logical_key=key)
        await session.commit()
        assert reservation is not None
        assert reservation.status is ReservationStatus.RESERVED

    async with SessionFactory() as session:
        snapshot = await quota.snapshot(session, user_id)
        assert snapshot["reserved"] == 4
        assert snapshot["available"] == 1

        attached = await session.get(QuotaReservation, reservation.id)
        await quota.settle(session, attached, 3, reason="成功 3 张")
        await session.commit()

    async with SessionFactory() as session:
        attached = await session.get(QuotaReservation, reservation.id)
        snapshot = await quota.snapshot(session, user_id)
        assert snapshot["reserved"] == 0
        assert snapshot["consumed"] == 3
        assert snapshot["available"] == 2

        # 重复结算不重复扣减
        await quota.settle(session, attached, 3)
        await session.commit()
        snapshot = await quota.snapshot(session, user_id)
        assert snapshot["consumed"] == 3

        actions = list(
            await session.scalars(
                select(QuotaLedger.action).where(QuotaLedger.user_id == user_id)
            )
        )
        assert [action.value for action in actions] == ["reserve", "consume", "release"]


async def test_failure_releases_full_reservation(enforce) -> None:
    user_id = await _user()
    async with SessionFactory() as session:
        reservation = await quota.reserve(
            session, user_id, 2, logical_key=f"test:{uuid.uuid4()}"
        )
        await session.commit()

    async with SessionFactory() as session:
        attached = await session.get(QuotaReservation, reservation.id)
        await quota.release(session, attached, reason="厂商失败")
        await session.commit()
        snapshot = await quota.snapshot(session, user_id)
        assert snapshot["reserved"] == 0
        assert snapshot["consumed"] == 0
        assert snapshot["available"] == snapshot["daily_limit"]


async def test_concurrent_reservations_never_oversell(enforce) -> None:
    user_id = await _user()

    async def attempt() -> bool:
        async with SessionFactory() as session:
            try:
                await quota.reserve(
                    session, user_id, 4, logical_key=f"test:{uuid.uuid4()}"
                )
            except quota.QuotaExhausted:
                await session.rollback()
                return False
            await session.commit()
            return True

    results = await asyncio.gather(attempt(), attempt())
    assert sorted(results) == [False, True]

    async with SessionFactory() as session:
        bucket = await session.scalar(
            select(QuotaBucket).where(QuotaBucket.user_id == user_id)
        )
        assert bucket is not None
        assert bucket.reserved <= bucket.limit
        assert bucket.available >= 0


async def test_local_tools_do_not_consume() -> None:
    assert quota.units_for("crop_canvas", {}) == 0
    assert quota.units_for("adjust_image", {"brightness": 0.2}) == 0
    assert quota.units_for("remove_background", {}) == 0
    assert quota.units_for("prepare_delivery_sizes", {}) == 0
    assert quota.units_for("generate_image", {"count": 4}) == 4
    assert quota.units_for("replace_background", {"count": 2}) == 2


def test_batch_units_expand_ai_chain() -> None:
    params = {
        "asset_ids": ["a", "b"],
        "operations": [
            {"tool": "replace_background", "params": {"prompt": "x"}},
            {"tool": "prepare_delivery_sizes", "params": {"ratios": ["1:1", "4:5", "9:16"]}},
            {"tool": "expand_canvas", "params": {"ratio": "16:9"}},
        ],
    }
    # 每张素材：换背景 1 次，投放尺寸本地扩成 3 帧，再各扩图 1 次 → 4 次
    assert batch_units(params) == 8


async def test_reservation_belongs_to_original_day(enforce) -> None:
    user_id = await _user()
    day = date.today() - timedelta(days=1)

    async with SessionFactory() as session:
        reservation = await quota.reserve(
            session,
            user_id,
            1,
            logical_key=f"test:{uuid.uuid4()}",
            quota_date=day,
        )
        await session.commit()

    async with SessionFactory() as session:
        attached = await session.get(QuotaReservation, reservation.id)
        await quota.settle(session, attached, 1)
        await session.commit()

        old = await session.scalar(
            select(QuotaBucket).where(
                QuotaBucket.user_id == user_id, QuotaBucket.quota_date == day
            )
        )
        today = await quota.snapshot(session, user_id)
        assert old is not None and old.consumed == 1
        assert today["consumed"] == 0
        assert today["available"] == today["daily_limit"]


async def test_exhausted_api_returns_structured_409(
    client: httpx.AsyncClient, enforce
) -> None:
    credentials = {
        "username": f"test_quota_api_{uuid.uuid4().hex[:8]}",
        "password": "secret123",
    }
    assert (await client.post("/api/auth/register", json=credentials)).status_code == 201

    async with SessionFactory() as session:
        user = await session.scalar(
            select(User).where(User.username == credentials["username"])
        )
        assert user is not None
        snapshot = await quota.snapshot(session, user.id)
        await quota.reserve(
            session,
            user.id,
            snapshot["daily_limit"] + snapshot["adjustment"],
            logical_key=f"test:{uuid.uuid4()}",
        )
        await session.commit()

    response = await client.post(
        "/api/generations",
        json={"prompt": "白底马克杯", "ratio": "1:1", "count": 2},
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "QUOTA_EXHAUSTED"
    assert detail["required"] == 2
    assert detail["available"] == 0
    assert detail["reset_at"]
