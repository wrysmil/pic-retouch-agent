import enum
import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import UUIDBase, enum_column


class AssetKind(enum.StrEnum):
    """资源类型/用途"""
    ORIGINAL = "original"  # 用户上传的原始图片
    GENERATED = "generated"  # AI 生成的内容
    SUBJECT = "subject"  # 主体抠图（去背景后的前景对象）
    BACKGROUND = "background"  # 背景图
    MASK = "mask"  # 蒙版（用于区域选择或保护）
    MARKETING = "marketing"  # 营销素材（用于展示或分享）
    EXPORT = "export"  # 导出的最终成品


class AssetSource(enum.StrEnum):
    """资源来源"""
    UPLOAD = "upload"  # 用户上传
    GENERATE = "generate"  # AI 生成
    TOOL = "tool"  # 工具处理（裁剪、滤镜、编辑等）


class Asset(UUIDBase):
    __tablename__ = "assets"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[AssetKind] = mapped_column(enum_column(AssetKind))
    source: Mapped[AssetSource] = mapped_column(enum_column(AssetSource))
    storage_key: Mapped[str] = mapped_column(String(255), unique=True)
    image_format: Mapped[str] = mapped_column(String(8))
    width: Mapped[int]
    height: Mapped[int]
    size_bytes: Mapped[int]
    has_alpha: Mapped[bool]