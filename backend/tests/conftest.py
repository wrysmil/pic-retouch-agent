import time
import uuid

import httpx
import pytest
from cryptography.fernet import Fernet
from httpx import ASGITransport
from sqlalchemy import delete, select, update

from app.config import get_settings
from app.db import SessionFactory
from app.main import app
from app.models import (
    AdminAuditLog,
    AdapterType,
    AgentRun,
    ModelConnection,
    ModelConnectionVersion,
    ModelDefinition,
    ModelType,
    RuntimeConfigState,
    RuntimeConfigVersion,
    ToolRun,
    User,
    UserRole,
)
from app.providers import MockImageProvider
from app.security import hash_password
from app.security_vault import encrypt_secret
from app.storage import ensure_bucket

# 测试账号统一此前缀，清理时只删这些行，避免误清开发库里的真实用户
TEST_USER_PREFIX = "test_"


async def unbind_run_versions(session, versions) -> None:
    """把历史任务对给定版本的引用摘掉（RESTRICT 外键，删版本前必须先解绑）。"""
    await session.execute(
        update(ToolRun)
        .where(ToolRun.runtime_config_version_id.in_(versions))
        .values(runtime_config_version_id=None)
    )
    await session.execute(
        update(AgentRun)
        .where(AgentRun.runtime_config_version_id.in_(versions))
        .values(runtime_config_version_id=None)
    )


async def repair_runtime_state(session) -> None:
    """运行指针被清理掉后指回剩下的最新版本。

    测试里发布新版本会把 state 指过去；那些版本被删掉后若不修复指针，
    同一 session 里后续的用例会因为「没有生效的运行配置」而整片失败。
    调用方负责 commit。
    """
    state = await session.scalar(select(RuntimeConfigState).limit(1))
    if state is not None and state.current_version_id is not None:
        if await session.get(RuntimeConfigVersion, state.current_version_id) is not None:
            return

    latest = await session.scalar(
        select(RuntimeConfigVersion).order_by(RuntimeConfigVersion.version_seq.desc()).limit(1)
    )
    if state is None:
        if latest is not None:
            session.add(
                RuntimeConfigState(current_version_id=latest.id, revision=latest.version_seq)
            )
        return
    state.current_version_id = latest.id if latest is not None else None
    if latest is not None:
        state.revision = max(state.revision, latest.version_seq)


async def purge_actor_model_config(session, actor_id) -> None:
    """按外键依赖顺序清掉某个管理员在模型配置里留下的行，并修复运行指针。

    users 被 model_connection_versions.created_by 与 runtime_config_versions.published_by
    以 RESTRICT 引用，所以删账号前必须先把这些行摘干净，否则 fixture teardown
    会炸外键，且残留行会让下一次运行撞上 slug 重复。调用方负责 commit。

    注意：外键 id 必须先取成普通列表。若把它们留成子查询，等版本行删掉之后
    子查询就查不到东西了，连接行会残留（这里踩过一次）。
    """
    connection_ids = list(
        await session.scalars(
            select(ModelConnectionVersion.connection_id).where(
                ModelConnectionVersion.created_by == actor_id
            )
        )
    )
    version_ids = list(
        await session.scalars(
            select(RuntimeConfigVersion.id).where(RuntimeConfigVersion.published_by == actor_id)
        )
    )

    if version_ids:
        await unbind_run_versions(session, version_ids)
        await session.execute(
            delete(RuntimeConfigState).where(RuntimeConfigState.current_version_id.in_(version_ids))
        )
    await session.execute(
        delete(RuntimeConfigVersion).where(RuntimeConfigVersion.published_by == actor_id)
    )
    if connection_ids:
        await session.execute(
            delete(ModelDefinition).where(ModelDefinition.connection_id.in_(connection_ids))
        )
    await session.execute(
        delete(ModelConnectionVersion).where(ModelConnectionVersion.created_by == actor_id)
    )
    if connection_ids:
        await session.execute(delete(ModelConnection).where(ModelConnection.id.in_(connection_ids)))
    await session.execute(delete(AdminAuditLog).where(AdminAuditLog.actor_id == actor_id))
    await session.execute(delete(User).where(User.id == actor_id))
    await repair_runtime_state(session)


async def _publish_mock_runtime() -> None:
    """清理旧的运行版本、连接、模型，并发布一份 Mock 运行配置。"""
    settings = get_settings()
    if not settings.secret_enc_key:
        # 测试期缺主密钥时随机生成，进程内有效
        settings.secret_enc_key = Fernet.generate_key().decode()

    async with SessionFactory() as session:
        # 历史任务（tool_runs / agent_runs）通过 runtime_config_version_id 引用版本，
        # 且是 RESTRICT；不先摘掉这层引用，删版本会撞外键约束。
        # 这里只解绑、不删任务行，避免动到开发库里的任务与产物记录。
        await unbind_run_versions(
            session, select(RuntimeConfigVersion.id)
        )
        # 先删状态指针再删版本：state.current_version_id 外键指向 version，
        # 顺序反了同样会撞外键约束
        await session.execute(delete(RuntimeConfigState))
        await session.execute(delete(RuntimeConfigVersion))
        await session.execute(delete(ModelDefinition))
        await session.execute(delete(ModelConnectionVersion))
        await session.execute(delete(ModelConnection))
        await session.commit()

        actor = await session.scalar(select(User).where(User.role == UserRole.ADMIN))
        if actor is None:
            actor = User(
                username="__test_runtime_admin",
                password_hash=hash_password("placeholder"),
                role=UserRole.ADMIN,
            )
            session.add(actor)
            await session.commit()
            await session.refresh(actor)

        conn = ModelConnection(
            slug="test-mock-conn",
            vendor="mock",
            adapter_type=AdapterType.MOCK,
            display_name="Test Mock Connection",
        )
        session.add(conn)
        await session.flush()
        conn_version = ModelConnectionVersion(
            connection_id=conn.id,
            version_seq=1,
            base_url="http://localhost/mock",
            encrypted_api_key=encrypt_secret("test-mock-key"),
            created_by=actor.id,
        )
        session.add(conn_version)
        await session.flush()
        conn.current_version_id = conn_version.id

        text_def = ModelDefinition(
            slug="test-mock-text",
            connection_id=conn.id,
            vendor_model_id="mock-text",
            display_name="Test Text",
            model_type=ModelType.TEXT,
        )
        image_def = ModelDefinition(
            slug="test-mock-image",
            connection_id=conn.id,
            vendor_model_id="mock-image",
            display_name="Test Image",
            model_type=ModelType.IMAGE,
        )
        session.add_all([text_def, image_def])
        await session.flush()

        from datetime import UTC, datetime

        version = RuntimeConfigVersion(
            version_seq=1,
            text_model_id=text_def.id,
            text_connection_version_id=conn_version.id,
            image_model_id=image_def.id,
            image_connection_version_id=conn_version.id,
            runtime_params={},
            test_summary={},
            note="test fixture",
            published_by=actor.id,
            published_at=datetime.now(UTC),
        )
        session.add(version)
        await session.flush()
        state = RuntimeConfigState(current_version_id=version.id, revision=1)
        session.add(state)
        await session.commit()


@pytest.fixture(scope="session", autouse=True)
def bucket():
    ensure_bucket()


@pytest.fixture(scope="session", autouse=True)
async def test_runtime_config():
    """session 级一次性发布 mock 运行配置。"""
    await _publish_mock_runtime()
    yield


@pytest.fixture(scope="session", autouse=True)
def sync_agent_planning():
    """现有用例依赖 POST 返回时计划已就绪；异步规划由专门用例显式打开。"""
    settings = get_settings()
    original, settings.agent_async_planning = settings.agent_async_planning, False
    yield
    settings.agent_async_planning = original


@pytest.fixture(scope="session", autouse=True)
def shadow_quota():
    """现有用例会连续生成多张图；默认关闭强制拦截，仍保留预占与流水。

    额度相关用例在自身作用域内把 quota_enforce 改回 True。
    """
    settings = get_settings()
    original, settings.quota_enforce = settings.quota_enforce, False
    yield
    settings.quota_enforce = original


@pytest.fixture(scope="session", autouse=True)
def corner_matting():
    settings = get_settings()
    original, settings.matting_provider = settings.matting_provider, "corner"
    yield
    settings.matting_provider = original


@pytest.fixture(scope="session", autouse=True)
def skip_ocr():
    settings = get_settings()
    original, settings.ocr_provider = settings.ocr_provider, "none"
    yield
    settings.ocr_provider = original


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def credentials() -> dict[str, str]:
    return {"username": f"{TEST_USER_PREFIX}{uuid.uuid4().hex[:10]}", "password": "secret123"}


@pytest.fixture
def other_credentials() -> dict[str, str]:
    return {"username": f"{TEST_USER_PREFIX}other_{uuid.uuid4().hex[:8]}", "password": "secret123"}


@pytest.fixture
async def admin_credentials() -> dict:
    """测试用管理员账号：fixture 负责创建并清理。

    放在 conftest 而不是某个测试模块里：test_admin_users 与 test_admin_config
    都要用它，而模块级 fixture 不能跨模块共享。
    """
    username = f"test_admin_{int(time.time() * 1000) % 10**8}_{uuid.uuid4().hex[:6]}"
    password = "AdminPass123!"
    async with SessionFactory() as session:
        admin = User(
            username=username,
            password_hash=hash_password(password),
            role=UserRole.ADMIN,
            is_active=True,
        )
        session.add(admin)
        await session.commit()
        await session.refresh(admin)
        admin_id = admin.id
    yield {"username": username, "password": password, "id": admin_id}
    # 该管理员可能经后台接口发布过运行版本（见 test_admin_config 的回滚流程），
    # 清账号前要按依赖顺序摘掉模型配置行，否则撞 users 上的 RESTRICT 外键
    async with SessionFactory() as session:
        await purge_actor_model_config(session, admin_id)
        await session.commit()


@pytest.fixture
async def admin_client(client: httpx.AsyncClient, admin_credentials: dict) -> httpx.AsyncClient:
    response = await client.post(
        "/api/auth/login",
        json={"username": admin_credentials["username"], "password": admin_credentials["password"]},
    )
    assert response.status_code == 200
    return client


@pytest.fixture(autouse=True)
async def cleanup_users():
    yield
    async with SessionFactory() as session:
        # 测试账号可能创建过模型配置行，而 users 被这些行以 RESTRICT 引用，
        # 所以不能直接批量删号：先按依赖顺序摘干净每个账号名下的配置。
        # 其余归属账号的数据（任务、素材、编辑会话）都是 CASCADE，删号时自动清掉。
        user_ids = list(
            await session.scalars(
                select(User.id).where(User.username.startswith(TEST_USER_PREFIX))
            )
        )
        for user_id in user_ids:
            await purge_actor_model_config(session, user_id)
        await session.execute(delete(AdminAuditLog).where(AdminAuditLog.target_kind == "user"))
        await session.commit()


__all__ = ["MockImageProvider"]