"""免费会员额度接口的请求与响应模型。"""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class VipOut(BaseModel):
    status: str = "coming_soon"
    display_name: str = "VIP 会员"
    message: str = "更多权益即将开放"


class EntitlementsOut(BaseModel):
    membership_type: str
    display_name: str
    quota_date: date
    daily_limit: int
    adjustment: int
    reserved: int
    consumed: int
    available: int
    counting_unit: str
    timezone: str
    reset_at: datetime
    policy_version_id: uuid.UUID
    policy_version_seq: int
    vip: VipOut


class EstimateIn(BaseModel):
    tool: str = Field(min_length=1, max_length=48)
    params: dict = {}


class EstimateOut(BaseModel):
    tool: str
    required: int
    available: int
    affordable: bool
    reset_at: datetime
    counting_unit: str = "image"


class LedgerEntryOut(BaseModel):
    id: uuid.UUID
    action: str
    units: int
    available_after: int
    reason: str | None
    reservation_id: uuid.UUID | None
    created_at: datetime

    @classmethod
    def of(cls, entry) -> "LedgerEntryOut":
        return cls(
            id=entry.id,
            action=entry.action.value,
            units=entry.units,
            available_after=entry.available_after,
            reason=entry.reason,
            reservation_id=entry.reservation_id,
            created_at=entry.created_at,
        )


class LedgerPageOut(BaseModel):
    total: int
    items: list[LedgerEntryOut]


class PolicyCreateIn(BaseModel):
    daily_limit: int = Field(ge=0, le=1000)
    effective_from: date | None = None
    note: str | None = Field(default=None, max_length=200)


class PolicyOut(BaseModel):
    id: uuid.UUID
    version_seq: int
    daily_limit: int
    counting_unit: str
    timezone: str
    effective_from: date
    published_by: uuid.UUID | None
    note: str | None
    created_at: datetime

    @classmethod
    def of(cls, policy) -> "PolicyOut":
        return cls(
            id=policy.id,
            version_seq=policy.version_seq,
            daily_limit=policy.daily_limit,
            counting_unit=policy.counting_unit,
            timezone=policy.timezone,
            effective_from=policy.effective_from,
            published_by=policy.published_by,
            note=policy.note,
            created_at=policy.created_at,
        )


class OpenReservationOut(BaseModel):
    id: uuid.UUID
    units: int
    settled: int
    released: int
    status: str
    run_id: uuid.UUID | None
    turn_id: uuid.UUID | None
    step_id: str | None
    expires_at: datetime | None
    created_at: datetime

    @classmethod
    def of(cls, row) -> "OpenReservationOut":
        return cls(
            id=row.id,
            units=row.units,
            settled=row.settled,
            released=row.released,
            status=row.status.value,
            run_id=row.run_id,
            turn_id=row.turn_id,
            step_id=row.step_id,
            expires_at=row.expires_at,
            created_at=row.created_at,
        )


class AdminUserQuotaOut(BaseModel):
    quota_date: date
    limit: int
    adjustment: int
    reserved: int
    consumed: int
    available: int
    reset_at: datetime
    policy_version_id: uuid.UUID
    policy_version_seq: int
    open_reservations: list[OpenReservationOut] = []


class AdjustmentIn(BaseModel):
    units: int = Field(description="正数增加、负数扣减；不能为 0")
    reason: str = Field(min_length=2, max_length=200)
    quota_date: date | None = None


class ReleaseReservationIn(BaseModel):
    reason: str = Field(min_length=2, max_length=200)
