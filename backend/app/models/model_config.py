"""模型运行配置相关表。

数据按版本化方式组织：
- ModelConnection：稳定的逻辑连接（如「百炼生产账号」）。
- ModelConnectionVersion：连接的不可变版本，含 URL / 加密密钥 / 非敏感参数；编辑产生新版本。
- ModelDefinition：模型定义，引用连接 + 厂商模型 ID + 类型（文本/生图）+ 启用状态。
- RuntimeConfigVersion：把"文本/生图模型绑定 + 自由参数"冻结成一个发布版本。
- RuntimeConfigState：唯一当前生效指针，配合 revision 做并发发布冲突检测。
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TIMESTAMPTZ, UUIDBase, enum_column


class AdapterType(enum.StrEnum):
    """已支持的厂商适配器。新增类型需同时实现对应的客户端工厂。"""

    DASHSCOPE = "dashscope"
    OPENAI_COMPAT = "openai_compat"  # 文本走 /compatible-mode/v1，OpenAI Chat Completions 协议
    OPENAI_IMAGE = "openai_image"  # 图像生成与编辑走 OpenAI Images API（gpt-image-* 等）
    TOOOKENS = "toookens"  # Toookens /v1/images：operation_mode 区分文生图/图生图，支持异步任务
    MINIMAX = "minimax"  # MiniMax /v1/chat/completions：文本规划，思考需拆分到 reasoning_content
    MOCK = "mock"


class ConnectionStatus(enum.StrEnum):
    """连接的活跃状态。已撤销的不允许新发布，但已被任务绑定的旧版本仍可继续完成。"""

    ACTIVE = "active"
    RETIRED = "retired"


class ModelType(enum.StrEnum):
    """模型类型：全局只维护两类，每类可有多个定义但同时只允许一个启用。"""

    TEXT = "text"  # 文本模型：承担规划/对话，可调用工具
    IMAGE = "image"  # 生图模型：承担图像生成/编辑/放大


class ModelStatus(enum.StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class ModelConnection(UUIDBase):
    """逻辑连接，与版本是多对一关系。"""

    __tablename__ = "model_connections"

    slug: Mapped[str] = mapped_column(String(64), unique=True)
    vendor: Mapped[str] = mapped_column(String(32))
    adapter_type: Mapped[AdapterType] = mapped_column(enum_column(AdapterType))
    display_name: Mapped[str] = mapped_column(String(128))
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), default=None
    )
    status: Mapped[ConnectionStatus] = mapped_column(
        enum_column(ConnectionStatus), default=ConnectionStatus.ACTIVE
    )


class ModelConnectionVersion(UUIDBase):
    """连接版本的不可变快照。新建连接或修改配置都新插入一行。"""

    __tablename__ = "model_connection_versions"

    connection_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("model_connections.id", ondelete="CASCADE"), index=True
    )
    version_seq: Mapped[int] = mapped_column(Integer)
    base_url: Mapped[str] = mapped_column(String(512))
    encrypted_api_key: Mapped[str] = mapped_column(Text)
    extra: Mapped[dict] = mapped_column(JSONB, default=dict)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )

    __table_args__ = (UniqueConstraint("connection_id", "version_seq", name="uq_conn_version"),)


class ModelDefinition(UUIDBase):
    """模型定义：引用一个连接（按其当前版本解析）+ 厂商模型 ID + 类型 + 启用状态。

    生图模型可选填 edit_vendor_model_id：厂商的编辑端点常与生成端点是不同模型
    （如百炼 qwen-image / qwen-image-edit-max）。留空则编辑复用生成模型 ID。
    """

    __tablename__ = "model_definitions"

    slug: Mapped[str] = mapped_column(String(64), unique=True)
    connection_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("model_connections.id", ondelete="RESTRICT"), index=True
    )
    vendor_model_id: Mapped[str] = mapped_column(String(128))
    edit_vendor_model_id: Mapped[str | None] = mapped_column(String(128), default=None)
    display_name: Mapped[str] = mapped_column(String(128))
    model_type: Mapped[ModelType] = mapped_column(enum_column(ModelType))
    param_schema: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[ModelStatus] = mapped_column(
        enum_column(ModelStatus), default=ModelStatus.ACTIVE
    )


class RuntimeConfigVersion(UUIDBase):
    """发布版本，落地两项模型绑定（文本 / 生图）+ 冻结的连接版本 + 参数 + 测试摘要。"""

    __tablename__ = "runtime_config_versions"

    version_seq: Mapped[int] = mapped_column(Integer, unique=True)
    text_model_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("model_definitions.id", ondelete="RESTRICT")
    )
    text_connection_version_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("model_connection_versions.id", ondelete="RESTRICT")
    )
    image_model_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("model_definitions.id", ondelete="RESTRICT")
    )
    image_connection_version_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("model_connection_versions.id", ondelete="RESTRICT")
    )
    runtime_params: Mapped[dict] = mapped_column(JSONB, default=dict)
    test_summary: Mapped[dict] = mapped_column(JSONB, default=dict)
    note: Mapped[str] = mapped_column(Text, default="")
    published_by: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    rolled_back_from: Mapped[int | None] = mapped_column(Integer, default=None)
    published_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ)


class RuntimeConfigState(UUIDBase):
    """唯一当前生效指针；与发布在同一事务里更新，事务回滚则维持原状。"""

    __tablename__ = "runtime_config_state"

    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("runtime_config_versions.id", ondelete="RESTRICT"),
        default=None,
    )
    revision: Mapped[int] = mapped_column(Integer, default=0)


__all__ = [
    "AdapterType",
    "ConnectionStatus",
    "ModelType",
    "ModelConnection",
    "ModelConnectionVersion",
    "ModelDefinition",
    "ModelStatus",
    "RuntimeConfigState",
    "RuntimeConfigVersion",
]