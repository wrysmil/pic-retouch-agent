"""模型运行配置服务。

连接/模型/版本的 CRUD、发布与回滚均在这里集中处理。
所有写操作都假设调用方负责 commit；并发发布用 expected_revision 控制。
"""

import uuid
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import (
    AdapterType,
    AdminAuditLog,
    AuditAction,
    ConnectionStatus,
    ModelConnection,
    ModelConnectionVersion,
    ModelDefinition,
    ModelStatus,
    ModelType,
    RuntimeConfigState,
    RuntimeConfigVersion,
)
from app.security_vault import encrypt_secret, mask_secret


class ConfigError(Exception):
    """配置变更前置检查失败。"""


class RevisionConflict(ConfigError):
    """并发发布冲突：expected_revision 与当前不一致。"""


class SlugTaken(ConfigError):
    """slug 已被占用。"""


class ConnectionNotFound(ConfigError):
    """指定连接不存在。"""


class ModelNotFound(ConfigError):
    """指定模型不存在。"""


async def list_connections(session: AsyncSession) -> list[ModelConnection]:
    result = await session.scalars(select(ModelConnection).order_by(ModelConnection.created_at))
    return list(result)


async def get_connection(session: AsyncSession, connection_id: uuid.UUID) -> ModelConnection:
    conn = await session.get(ModelConnection, connection_id)
    if conn is None:
        raise ConnectionNotFound
    return conn


async def create_connection(
    session: AsyncSession,
    actor_id: uuid.UUID,
    *,
    slug: str,
    vendor: str,
    adapter_type: AdapterType,
    display_name: str,
    base_url: str,
    api_key: str,
    extra: dict | None = None,
) -> ModelConnection:
    """新建连接并写入首个版本，密钥加密存储。"""
    conn = ModelConnection(
        slug=slug,
        vendor=vendor,
        adapter_type=adapter_type,
        display_name=display_name,
        status=ConnectionStatus.ACTIVE,
    )
    session.add(conn)
    try:
        await session.flush()
    except Exception:
        await session.rollback()
        raise SlugTaken("slug 已被其他连接占用")

    version = ModelConnectionVersion(
        connection_id=conn.id,
        version_seq=1,
        base_url=base_url,
        encrypted_api_key=encrypt_secret(api_key),
        extra=extra or {},
        created_by=actor_id,
    )
    session.add(version)
    await session.flush()
    conn.current_version_id = version.id
    await session.flush()

    session.add(
        AdminAuditLog(
            actor_id=actor_id,
            action="connection.created",
            target_kind="model_connection",
            target_id=conn.id,
            changes={"adapter_type": adapter_type.value, "version_seq": 1},
        )
    )
    return conn


async def new_connection_version(
    session: AsyncSession,
    actor_id: uuid.UUID,
    connection_id: uuid.UUID,
    *,
    base_url: str | None = None,
    api_key: str | None = None,
    extra: dict | None = None,
) -> ModelConnectionVersion:
    """为已有连接追加新版本。任一参数为 None 时沿用上一版本。"""
    conn = await get_connection(session, connection_id)
    latest = await session.get(ModelConnectionVersion, conn.current_version_id) if conn.current_version_id else None
    if latest is None:
        # 当前没有版本，先建 v1
        seq = 1
    else:
        seq = latest.version_seq + 1

    new_version = ModelConnectionVersion(
        connection_id=connection_id,
        version_seq=seq,
        base_url=base_url if base_url is not None else (latest.base_url if latest else ""),
        encrypted_api_key=(
            encrypt_secret(api_key) if api_key is not None else (latest.encrypted_api_key if latest else "")
        ),
        extra=extra if extra is not None else (latest.extra if latest else {}),
        created_by=actor_id,
    )
    session.add(new_version)
    await session.flush()
    conn.current_version_id = new_version.id
    await session.flush()

    session.add(
        AdminAuditLog(
            actor_id=actor_id,
            action="connection.version_added",
            target_kind="model_connection",
            target_id=connection_id,
            changes={"version_seq": seq},
        )
    )
    return new_version


async def revoke_connection_version(
    session: AsyncSession,
    actor_id: uuid.UUID,
    version_id: uuid.UUID,
) -> ModelConnectionVersion:
    version = await session.get(ModelConnectionVersion, version_id)
    if version is None:
        raise ConfigError("连接版本不存在")
    if version.revoked:
        return version
    version.revoked = True
    session.add(
        AdminAuditLog(
            actor_id=actor_id,
            action="connection.revoked",
            target_kind="model_connection_version",
            target_id=version_id,
            changes={},
        )
    )
    return version


async def list_models(session: AsyncSession) -> list[ModelDefinition]:
    result = await session.scalars(select(ModelDefinition).order_by(ModelDefinition.created_at))
    return list(result)


async def get_model(session: AsyncSession, model_id: uuid.UUID) -> ModelDefinition:
    model = await session.get(ModelDefinition, model_id)
    if model is None:
        raise ModelNotFound
    return model


async def create_model(
    session: AsyncSession,
    actor_id: uuid.UUID,
    *,
    slug: str,
    connection_id: uuid.UUID,
    vendor_model_id: str,
    display_name: str,
    model_type: ModelType,
    edit_vendor_model_id: str | None = None,
    param_schema: dict | None = None,
) -> ModelDefinition:
    """新建模型定义。每类同时只允许一个启用：若该类已有启用模型，新建的置为停用。"""
    await get_connection(session, connection_id)
    existing_active = await session.scalar(
        select(ModelDefinition).where(
            ModelDefinition.model_type == model_type,
            ModelDefinition.status == ModelStatus.ACTIVE,
        )
    )
    model = ModelDefinition(
        slug=slug,
        connection_id=connection_id,
        vendor_model_id=vendor_model_id,
        edit_vendor_model_id=edit_vendor_model_id or None,
        display_name=display_name,
        model_type=model_type,
        param_schema=param_schema or {},
        status=ModelStatus.DISABLED if existing_active else ModelStatus.ACTIVE,
    )
    session.add(model)
    try:
        await session.flush()
    except Exception:
        await session.rollback()
        raise SlugTaken("slug 已被其他模型占用")

    session.add(
        AdminAuditLog(
            actor_id=actor_id,
            action="model.created",
            target_kind="model_definition",
            target_id=model.id,
            changes={"connection_id": str(connection_id), "model_type": model_type.value},
        )
    )
    return model


async def _disable_others_of_type(
    session: AsyncSession, model_type: ModelType, keep_id: uuid.UUID
) -> None:
    """把同类型下除 keep_id 外的启用模型全部停用，维持“每类一个启用”。"""
    others = await session.scalars(
        select(ModelDefinition).where(
            ModelDefinition.model_type == model_type,
            ModelDefinition.status == ModelStatus.ACTIVE,
            ModelDefinition.id != keep_id,
        )
    )
    for other in others:
        other.status = ModelStatus.DISABLED


async def activate_model(
    session: AsyncSession, actor_id: uuid.UUID, model_id: uuid.UUID
) -> ModelDefinition:
    """启用某模型，并自动停用同类型的其他启用模型。"""
    model = await get_model(session, model_id)
    if model.status == ModelStatus.ACTIVE:
        return model
    model.status = ModelStatus.ACTIVE
    await _disable_others_of_type(session, model.model_type, model.id)
    session.add(
        AdminAuditLog(
            actor_id=actor_id,
            action="model.activated",
            target_kind="model_definition",
            target_id=model_id,
            changes={"model_type": model.model_type.value},
        )
    )
    return model


async def disable_model(session: AsyncSession, actor_id: uuid.UUID, model_id: uuid.UUID) -> ModelDefinition:
    model = await get_model(session, model_id)
    if model.status == ModelStatus.DISABLED:
        return model
    model.status = ModelStatus.DISABLED
    session.add(
        AdminAuditLog(
            actor_id=actor_id,
            action="model.disabled",
            target_kind="model_definition",
            target_id=model_id,
            changes={},
        )
    )
    return model


async def get_state(session: AsyncSession) -> RuntimeConfigState:
    """始终返回唯一的状态行；不存在则创建。"""
    state = await session.scalar(select(RuntimeConfigState).limit(1))
    if state is None:
        state = RuntimeConfigState(current_version_id=None, revision=0)
        session.add(state)
        await session.flush()
    return state


async def list_versions(session: AsyncSession, limit: int = 50) -> list[RuntimeConfigVersion]:
    result = await session.scalars(
        select(RuntimeConfigVersion)
        .order_by(RuntimeConfigVersion.version_seq.desc())
        .limit(limit)
    )
    return list(result)


async def get_version_by_seq(session: AsyncSession, seq: int) -> RuntimeConfigVersion:
    ver = await session.scalar(
        select(RuntimeConfigVersion).where(RuntimeConfigVersion.version_seq == seq)
    )
    if ver is None:
        raise ConfigError("指定版本不存在")
    return ver


async def get_current_version(session: AsyncSession) -> RuntimeConfigVersion | None:
    state = await get_state(session)
    if state.current_version_id is None:
        return None
    return await session.get(RuntimeConfigVersion, state.current_version_id)


async def publish_version(
    session: AsyncSession,
    actor_id: uuid.UUID,
    *,
    text_model_id: uuid.UUID,
    image_model_id: uuid.UUID,
    runtime_params: dict | None = None,
    test_summary: dict | None = None,
    note: str = "",
    expected_revision: int,
) -> RuntimeConfigVersion:
    """发布新版本。expected_revision 与 state 不一致则抛 RevisionConflict。"""
    state = await get_state(session)
    if state.revision != expected_revision:
        raise RevisionConflict(
            f"配置已被并发更新（当前 revision={state.revision}，期望 {expected_revision}），请刷新后重试"
        )

    text_model = await get_model(session, text_model_id)
    image_model = await get_model(session, image_model_id)
    if text_model.model_type != ModelType.TEXT:
        raise ConfigError("文本槽位必须绑定文本类型的模型")
    if image_model.model_type != ModelType.IMAGE:
        raise ConfigError("生图槽位必须绑定生图类型的模型")

    # 两个模型各自从其连接取出当前版本（同一发布版本内两个连接版本可能不同）
    async def _conn_ver(model_id: uuid.UUID) -> uuid.UUID:
        model = await get_model(session, model_id)
        conn = await get_connection(session, model.connection_id)
        if conn.current_version_id is None:
            raise ConfigError(f"模型 {model.slug} 关联的连接没有可用版本")
        return conn.current_version_id

    text_cv = await _conn_ver(text_model_id)
    image_cv = await _conn_ver(image_model_id)

    last = await session.scalar(select(RuntimeConfigVersion).order_by(RuntimeConfigVersion.version_seq.desc()))
    next_seq = (last.version_seq + 1) if last else 1

    published_at = datetime.now(UTC)
    version = RuntimeConfigVersion(
        version_seq=next_seq,
        text_model_id=text_model_id,
        text_connection_version_id=text_cv,
        image_model_id=image_model_id,
        image_connection_version_id=image_cv,
        runtime_params=runtime_params or {},
        test_summary=test_summary or {},
        note=note,
        published_by=actor_id,
        published_at=published_at,
    )
    session.add(version)
    await session.flush()

    state.current_version_id = version.id
    state.revision = state.revision + 1
    session.add(
        AdminAuditLog(
            actor_id=actor_id,
            action="config.published",
            target_kind="runtime_config_version",
            target_id=version.id,
            changes={"version_seq": next_seq},
        )
    )
    return version


async def rollback_to(
    session: AsyncSession,
    actor_id: uuid.UUID,
    *,
    target_seq: int,
    expected_revision: int,
) -> RuntimeConfigVersion:
    """把历史某个版本复制成新版本号发布；保留完整历史。"""
    state = await get_state(session)
    if state.revision != expected_revision:
        raise RevisionConflict(
            f"配置已被并发更新（当前 revision={state.revision}，期望 {expected_revision}）"
        )
    target = await get_version_by_seq(session, target_seq)
    last = await session.scalar(select(RuntimeConfigVersion).order_by(RuntimeConfigVersion.version_seq.desc()))
    next_seq = (last.version_seq + 1) if last else 1
    now = datetime.now(UTC)
    new_version = RuntimeConfigVersion(
        version_seq=next_seq,
        text_model_id=target.text_model_id,
        text_connection_version_id=target.text_connection_version_id,
        image_model_id=target.image_model_id,
        image_connection_version_id=target.image_connection_version_id,
        runtime_params=target.runtime_params,
        test_summary=target.test_summary,
        note=f"回滚自版本 {target_seq}",
        published_by=actor_id,
        published_at=now,
        rolled_back_from=target_seq,
    )
    session.add(new_version)
    await session.flush()
    state.current_version_id = new_version.id
    state.revision = state.revision + 1
    session.add(
        AdminAuditLog(
            actor_id=actor_id,
            action="config.rolled_back",
            target_kind="runtime_config_version",
            target_id=new_version.id,
            changes={"from_seq": target_seq, "to_seq": next_seq},
        )
    )
    return new_version


async def connection_key_mask(version: ModelConnectionVersion) -> str:
    """给前端展示密钥尾号。"""
    from app.security_vault import decrypt_secret

    try:
        plain = decrypt_secret(version.encrypted_api_key)
    except Exception:
        return "****"
    return mask_secret(plain)