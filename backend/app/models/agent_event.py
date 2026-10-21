import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import UUIDBase


class AgentEvent(UUIDBase):
    """轮次内的持久事件。Redis 只负责唤醒，断线补洞以这张表为准。"""

    __tablename__ = "agent_events"
    __table_args__ = (UniqueConstraint("turn_id", "seq", name="uq_agent_event_seq"),)

    turn_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True
    )
    seq: Mapped[int] = mapped_column(nullable=False)
    type: Mapped[str] = mapped_column(String(48), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
