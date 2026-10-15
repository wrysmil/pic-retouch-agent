"""后台模型配置管理。

- /api/admin/model-connections CRUD + 版本 + 测试 + 撤销
- /api/admin/models CRUD
- /api/admin/model-config current / publish / rollback / versions / test

所有写操作要求管理员身份（AdminUser 依赖）。
"""

import time
import uuid
from datetime import UTC, datetime as _dt

from fastapi import APIRouter, HTTPException, status

from app.db import SessionDep
from app.deps import AdminUser
from app.models import AdminAuditLog, User
from app.providers import GenerateRequest, ProviderError
from app.schemas.admin_config import (
    AdminConnectionCreate,
    AdminConnectionOut,
    AdminConnectionVersionCreate,
    AdminModelCreate,
    AdminModelOut,
    AdminRuntimeOut,
    AdminRuntimePublish,
    AdminRuntimeRollback,
    AdminRuntimeVersionOut,
    AdminTestRequest,
    AdminTestResult,
)
from app.security_vault import DecryptionFailed, decrypt_secret
from app.services import model_config
from app.services.model_runtime import (
    IncompatibleRuntime,
    RuntimeMissing,
    get_image_client,
    get_planner,
)
from app.services.provider_url import ProviderUrlRejected, validate_provider_url

router = APIRouter(prefix="/admin/model-config", tags=["admin:config"])


# ---- connections ----

async def _connection_view(session, conn, base_url: str = "", key_mask: str = "") -> AdminConnectionOut:
    seq = None
    if conn.current_version_id:
        from sqlalchemy import select

        version = await session.get(__import__("app.models", fromlist=["ModelConnectionVersion"]).ModelConnectionVersion, conn.current_version_id)
        if version is not None:
            seq = version.version_seq
    return AdminConnectionOut(
        id=conn.id,
        slug=conn.slug,
        vendor=conn.vendor,
        adapter_type=conn.adapter_type.value,
        display_name=conn.display_name,
        status=conn.status.value,
        current_version_id=conn.current_version_id,
        current_version_seq=seq,
        base_url=base_url,
        key_mask=key_mask,
        created_at=conn.created_at,
    )


@router.get("/connections", response_model=list[AdminConnectionOut])
async def list_connections(_actor: AdminUser, session: SessionDep) -> list[AdminConnectionOut]:
    rows = await model_config.list_connections(session)
    out: list[AdminConnectionOut] = []
    for conn in rows:
        out.append(await _connection_view(session, conn))
    return out


@router.post(
    "/connections",
    response_model=AdminConnectionOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_connection(
    body: AdminConnectionCreate,
    actor: AdminUser,
    session: SessionDep,
) -> AdminConnectionOut:
    try:
        normalized_url = validate_provider_url(body.base_url)
    except ProviderUrlRejected as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    from app.models import AdapterType

    try:
        conn = await model_config.create_connection(
            session,
            actor.id,
            slug=body.slug,
            vendor=body.vendor,
            adapter_type=AdapterType(body.adapter_type),
            display_name=body.display_name,
            base_url=normalized_url,
            api_key=body.api_key,
            extra=body.extra,
        )
    except model_config.SlugTaken as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await session.commit()
    await session.refresh(conn)
    return await _connection_view(session, conn, base_url=normalized_url, key_mask="****")


@router.post(
    "/connections/{connection_id}/versions",
    response_model=AdminConnectionOut,
)
async def add_version(
    connection_id: uuid.UUID,
    payload: AdminConnectionVersionCreate,
    actor: AdminUser,
    session: SessionDep,
) -> AdminConnectionOut:
    if payload.base_url is not None:
        try:
            payload.base_url = validate_provider_url(payload.base_url)
        except ProviderUrlRejected as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    try:
        await model_config.new_connection_version(
            session,
            actor.id,
            connection_id,
            base_url=payload.base_url,
            api_key=payload.api_key,
            extra=payload.extra,
        )
    except model_config.ConnectionNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "连接不存在") from None
    await session.commit()
    conn = await model_config.get_connection(session, connection_id)
    return await _connection_view(session, conn)


@router.post(
    "/connections/{connection_id}/versions/{version_id}/revoke",
    response_model=AdminConnectionOut,
)
async def revoke_version(
    connection_id: uuid.UUID,
    version_id: uuid.UUID,
    actor: AdminUser,
    session: SessionDep,
) -> AdminConnectionOut:
    try:
        await model_config.revoke_connection_version(session, actor.id, version_id)
    except model_config.ConfigError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    await session.commit()
    conn = await model_config.get_connection(session, connection_id)
    return await _connection_view(session, conn)


# ---- models ----

@router.get("/models", response_model=list[AdminModelOut])
async def list_models(_actor: AdminUser, session: SessionDep) -> list[AdminModelOut]:
    rows = await model_config.list_models(session)
    return [AdminModelOut.model_validate(m) for m in rows]


@router.post(
    "/models",
    response_model=AdminModelOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_model(
    body: AdminModelCreate,
    actor: AdminUser,
    session: SessionDep,
) -> AdminModelOut:
    try:
        from app.models import ModelType

        model = await model_config.create_model(
            session,
            actor.id,
            slug=body.slug,
            connection_id=body.connection_id,
            vendor_model_id=body.vendor_model_id,
            edit_vendor_model_id=body.edit_vendor_model_id,
            display_name=body.display_name,
            model_type=ModelType(body.model_type),
            param_schema=body.param_schema,
        )
    except model_config.SlugTaken as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except model_config.ConnectionNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "关联连接不存在") from None
    await session.commit()
    await session.refresh(model)
    return AdminModelOut.model_validate(model)


@router.post("/models/{model_id}/activate", response_model=AdminModelOut)
async def activate_model(model_id: uuid.UUID, actor: AdminUser, session: SessionDep) -> AdminModelOut:
    """启用某模型；同类型的其他启用模型会被自动停用。"""
    try:
        model = await model_config.activate_model(session, actor.id, model_id)
    except model_config.ModelNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "模型不存在") from None
    await session.commit()
    await session.refresh(model)
    return AdminModelOut.model_validate(model)


@router.post("/models/{model_id}/disable", response_model=AdminModelOut)
async def disable_model(model_id: uuid.UUID, actor: AdminUser, session: SessionDep) -> AdminModelOut:
    try:
        model = await model_config.disable_model(session, actor.id, model_id)
    except model_config.ModelNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "模型不存在") from None
    await session.commit()
    return AdminModelOut.model_validate(model)


# ---- runtime config ----

@router.get("/current", response_model=AdminRuntimeOut)
async def current_runtime(_actor: AdminUser, session: SessionDep) -> AdminRuntimeOut:
    state = await model_config.get_state(session)
    version = None
    if state.current_version_id:
        from sqlalchemy import select

        version = await session.get(__import__("app.models", fromlist=["RuntimeConfigVersion"]).RuntimeConfigVersion, state.current_version_id)
    if version is None:
        return AdminRuntimeOut(
            current_version_seq=None,
            revision=state.revision,
            published_at=None,
            published_by=None,
            note="",
            text_model_id=uuid.UUID(int=0),
            image_model_id=uuid.UUID(int=0),
        )
    return AdminRuntimeOut(
        current_version_seq=version.version_seq,
        revision=state.revision,
        published_at=version.published_at,
        published_by=version.published_by,
        note=version.note,
        text_model_id=version.text_model_id,
        image_model_id=version.image_model_id,
    )


@router.get("/versions", response_model=list[AdminRuntimeVersionOut])
async def list_versions(_actor: AdminUser, session: SessionDep) -> list[AdminRuntimeVersionOut]:
    rows = await model_config.list_versions(session)
    return [AdminRuntimeVersionOut.model_validate(r) for r in rows]


@router.post("/publish", response_model=AdminRuntimeOut)
async def publish_runtime(
    body: AdminRuntimePublish,
    actor: AdminUser,
    session: SessionDep,
) -> AdminRuntimeOut:
    try:
        version = await model_config.publish_version(
            session,
            actor.id,
            text_model_id=body.text_model_id,
            image_model_id=body.image_model_id,
            runtime_params=body.runtime_params,
            test_summary=body.test_summary,
            note=body.note,
            expected_revision=body.expected_revision,
        )
    except model_config.RevisionConflict as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except model_config.ModelNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "模型不存在") from exc
    except model_config.ConfigError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    await session.commit()
    await session.refresh(version)

    # 清空客户端缓存，让新版本生效
    from app.services.model_runtime import image_cache, planner_cache

    planner_cache().clear()
    image_cache().clear()

    return AdminRuntimeOut(
        current_version_seq=version.version_seq,
        revision=(await model_config.get_state(session)).revision,
        published_at=version.published_at,
        published_by=version.published_by,
        note=version.note,
        text_model_id=version.text_model_id,
        image_model_id=version.image_model_id,
    )


@router.post("/rollback", response_model=AdminRuntimeOut)
async def rollback_runtime(
    body: AdminRuntimeRollback,
    actor: AdminUser,
    session: SessionDep,
) -> AdminRuntimeOut:
    try:
        version = await model_config.rollback_to(
            session,
            actor.id,
            target_seq=body.target_seq,
            expected_revision=body.expected_revision,
        )
    except model_config.RevisionConflict as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except model_config.ConfigError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    await session.commit()
    await session.refresh(version)

    from app.services.model_runtime import image_cache, planner_cache

    planner_cache().clear()
    image_cache().clear()

    return AdminRuntimeOut(
        current_version_seq=version.version_seq,
        revision=(await model_config.get_state(session)).revision,
        published_at=version.published_at,
        published_by=version.published_by,
        note=version.note,
        text_model_id=version.text_model_id,
        image_model_id=version.image_model_id,
    )


@router.post("/test", response_model=AdminTestResult)
async def test_capability(
    body: AdminTestRequest,
    actor: AdminUser,
    session: SessionDep,
) -> AdminTestResult:
    """对当前生效的运行配置做一次真实调用，按能力分派。"""
    started = time.perf_counter()
    try:
        if body.capability == "text":
            from langchain_core.messages import HumanMessage

            version = await model_config.get_current_version(session)
            if version is None:
                raise RuntimeMissing("尚未发布运行配置")
            client = await get_planner(session, version.id)
            bound = client.client.bind_tools([])
            await bound.ainvoke([HumanMessage("只回复：就绪")])
        else:
            version = await model_config.get_current_version(session)
            if version is None:
                raise RuntimeMissing("尚未发布运行配置")
            client = await get_image_client(session, version.id)
            if body.capability == "image.generate":
                await client.provider.generate(
                    GenerateRequest(prompt=body.prompt, width=512, height=512, count=1)
                )
            else:
                from app.providers import EditRequest

                # 取当前画布失败时退化为空图：仅用作连通性测试
                await client.provider.edit(
                    EditRequest(prompt=body.prompt, image=b"\x89PNG\r\n\x1a\n", count=1)
                )
    except (ProviderError, RuntimeMissing, IncompatibleRuntime, DecryptionFailed) as exc:
        duration = int((time.perf_counter() - started) * 1000)
        session.add(
            AdminAuditLog(
                actor_id=actor.id,
                action="config.test_failed",
                target_kind="runtime_config",
                target_id=uuid.UUID(int=0),
                changes={"capability": body.capability, "error": str(exc)[:200]},
            )
        )
        await session.commit()
        return AdminTestResult(
            capability=body.capability,
            ok=False,
            detail=str(exc),
            duration_ms=duration,
        )
    except Exception as exc:
        duration = int((time.perf_counter() - started) * 1000)
        return AdminTestResult(
            capability=body.capability,
            ok=False,
            detail=f"{type(exc).__name__}: {exc}",
            duration_ms=duration,
        )

    duration = int((time.perf_counter() - started) * 1000)
    session.add(
        AdminAuditLog(
            actor_id=actor.id,
            action="config.test_succeeded",
            target_kind="runtime_config",
            target_id=uuid.UUID(int=0),
            changes={"capability": body.capability, "duration_ms": duration},
        )
    )
    await session.commit()
    return AdminTestResult(
        capability=body.capability,
        ok=True,
        detail="调用成功",
        duration_ms=duration,
    )