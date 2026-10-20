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
    AdminModelToggleOut,
    AdminRuntimeOut,
    AdminRuntimeApply,
    AdminRuntimePublish,
    AdminRuntimeRollback,
    AdminRuntimeVersionOut,
    AdminTestRequest,
    AdminTestResult,
)
from app.security_vault import DecryptionFailed, decrypt_secret, mask_secret
from app.services import model_config
from app.services.model_runtime import (
    IncompatibleRuntime,
    RuntimeMissing,
    get_image_client,
    get_planner,
)
from app.services.provider_url import ProviderUrlRejected, validate_connection_url

router = APIRouter(prefix="/admin/model-config", tags=["admin:config"])


def _clear_clients() -> None:
    """清掉按版本缓存的模型客户端，让新发布的配置立刻生效。"""
    from app.services.model_runtime import image_cache, planner_cache

    planner_cache().clear()
    image_cache().clear()


async def _auto_republish(session: SessionDep, actor: AdminUser):
    """启用状态变化后自动重发布运行版本，让「启用/停用」本身成为热更新开关。

    只有当当前生效版本与「文本槽位/生图槽位各自当前启用的模型」不一致时才发新版本，
    免得无关的启停操作把版本历史冲出一堆噪音。
    槽位凑不齐（某类一个启用模型都没有）时不发版：当前版本继续按原样跑。
    """
    from app.models import ModelType

    state = await model_config.get_state(session)
    current = await model_config.get_current_version(session)
    text = await model_config.get_active_model(session, ModelType.TEXT)
    image = await model_config.get_active_model(session, ModelType.IMAGE)
    if text is None or image is None:
        return None
    if (
        current is not None
        and current.text_model_id == text.id
        and current.image_model_id == image.id
    ):
        return None
    return await model_config.publish_version(
        session,
        actor.id,
        text_model_id=text.id,
        image_model_id=image.id,
        note=f"启用状态变化自动重发布：{text.display_name} / {image.display_name}",
        expected_revision=state.revision,
    )


# ---- connections ----

async def _connection_view(session, conn, base_url: str = "", key_mask: str = "") -> AdminConnectionOut:
    """组装一条连接的展示数据。

    base_url / key_mask 默认从当前版本里取：列表页要显示这两列，
    不取的话表格里永远是空的。密钥只给掩码，解不开（主密钥缺失或密文损坏）时留空，
    不能因为读不出密钥就让整页连接列表报错。
    """
    seq = None
    if conn.current_version_id:
        from app.models import ModelConnectionVersion

        version = await session.get(ModelConnectionVersion, conn.current_version_id)
        if version is not None:
            seq = version.version_seq
            if not base_url:
                base_url = version.base_url
            if not key_mask and version.encrypted_api_key:
                try:
                    key_mask = mask_secret(decrypt_secret(version.encrypted_api_key))
                except DecryptionFailed:
                    key_mask = ""
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
        normalized_url = validate_connection_url(body.adapter_type, body.base_url)
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
    # 地址策略按该连接自己的适配器走：mock 连接追加版本时同样不要求厂商地址
    conn = await model_config.get_connection(session, connection_id)
    if payload.base_url is not None:
        try:
            payload.base_url = validate_connection_url(
                conn.adapter_type.value, payload.base_url
            )
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


@router.post("/models/{model_id}/activate", response_model=AdminModelToggleOut)
async def activate_model(model_id: uuid.UUID, actor: AdminUser, session: SessionDep) -> AdminModelToggleOut:
    """启用某模型；同类型的其他启用模型会被自动停用。

    启用状态一变，「当前生效配置」就该跟着变，所以这里顺带重发布一次运行版本，
    让新提交的任务立刻用上新模型——不必再去点一次「发布新版本」。
    """
    try:
        model = await model_config.activate_model(session, actor.id, model_id)
    except model_config.ModelNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "模型不存在") from None
    version = await _auto_republish(session, actor)
    await session.commit()
    await session.refresh(model)
    if version is not None:
        _clear_clients()
    out = AdminModelToggleOut.model_validate(model)
    out.published_seq = version.version_seq if version is not None else None
    return out


@router.post("/models/{model_id}/disable", response_model=AdminModelToggleOut)
async def disable_model(model_id: uuid.UUID, actor: AdminUser, session: SessionDep) -> AdminModelToggleOut:
    """停用某模型。

    停用只影响「哪些模型可选」，不直接掐断正在跑的版本：
    该类型若还有别的启用模型，会自动重发布切过去；一个都没有时保持当前版本不动。
    """
    try:
        model = await model_config.disable_model(session, actor.id, model_id)
    except model_config.ModelNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "模型不存在") from None
    version = await _auto_republish(session, actor)
    await session.commit()
    out = AdminModelToggleOut.model_validate(model)
    out.published_seq = version.version_seq if version is not None else None
    if version is not None:
        _clear_clients()
    return out


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


@router.post("/apply", response_model=AdminRuntimeOut)
async def apply_runtime(
    body: AdminRuntimeApply,
    actor: AdminUser,
    session: SessionDep,
) -> AdminRuntimeOut:
    """一键切换：启用指定槽位的模型并立即发布生效。

    没指定的那个槽位沿用当前生效版本里的模型，所以「只把生图换成 mock」
    不必先准备一个本地规划模型。启用与版本指针在同一个事务里改完，只产生一个新版本。
    """
    from app.models import ModelType

    state = await model_config.get_state(session)
    if state.revision != body.expected_revision:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"配置已被并发更新（当前 revision={state.revision}，期望 {body.expected_revision}），请刷新后重试",
        )

    current = await model_config.get_current_version(session)
    text_id = body.text_model_id
    image_id = body.image_model_id
    if current is not None:
        text_id = text_id or current.text_model_id
        image_id = image_id or current.image_model_id
    if text_id is None or image_id is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "尚未发布运行配置，无法确定要保留的槽位模型"
        )

    try:
        text_model = await model_config.get_model(session, text_id)
        image_model = await model_config.get_model(session, image_id)
    except model_config.ModelNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "模型不存在") from None

    if text_model.model_type != ModelType.TEXT:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "文本槽位必须绑定文本类型的模型")
    if image_model.model_type != ModelType.IMAGE:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "生图槽位必须绑定生图类型的模型")

    # 启用目标模型（同类型的其它模型会被自动停用）
    await model_config.activate_model(session, actor.id, text_model.id)
    await model_config.activate_model(session, actor.id, image_model.id)

    version = await model_config.publish_version(
        session,
        actor.id,
        text_model_id=text_model.id,
        image_model_id=image_model.id,
        note=body.note or f"一键切换到 {text_model.display_name} / {image_model.display_name}",
        expected_revision=state.revision,
    )
    await session.commit()
    await session.refresh(version)
    _clear_clients()

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